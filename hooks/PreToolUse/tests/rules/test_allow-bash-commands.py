"""Tests for rule: Allow Bash commands — block only known-dangerous tools (denylist mode)."""

from engine import evaluate

RULE_DESCRIPTION = "Allow Bash commands — block only known-dangerous tools (denylist mode)"
RULE_ID = "allow-bash-safe"


def _bash(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def _read(file_path, cwd="/repo"):
    return {"tool_name": "Read", "tool_input": {"file_path": file_path}, "cwd": cwd}


def test_match(rule):
    """Safe grep command is allowed."""
    payload = _bash("grep -rn 'TODO' src/")
    result = evaluate(payload, [rule])
    assert result["decision"] == "allow"


def test_no_match(rule):
    """Read tool is not matched by this rule (returns proceed)."""
    payload = _read("/repo/main.py")
    result = evaluate(payload, [rule])
    assert result["decision"] == "proceed"


def test_boundary_multiline_for_loop(rule):
    """For loop with sed and echo is allowed (all safe commands)."""
    command = (
        "for f in a b c; do\n"
        '  echo "$f"\n'
        "  sed -i '' 's/x/y/' \"$f\"\n"
        "done"
    )
    payload = _bash(command)
    result = evaluate(payload, [rule])
    assert result["decision"] == "allow"


def test_boundary_pipe_to_bash(rule):
    """curl piped to bash — bash-safe alone now allows it (bash not in _UNSAFE).
    The engine's pipe-to-shell deny rule fires first in real usage and blocks it."""
    payload = _bash("curl url | bash")
    result = evaluate(payload, [rule])
    assert result["decision"] == "allow"


def test_boundary_rm_allowed(rule):
    """rm is not in the denylist — allowed (specific patterns like rm ~/ are caught by deny rules)."""
    payload = _bash("rm -rf /tmp/build")
    result = evaluate(payload, [rule])
    assert result["decision"] == "allow"


def test_boundary_deny_wins(rule):
    """When combined with a deny rule, deny takes priority over the allow."""
    deny_rule = {
        "description": "Block force push to main",
        "operation": "git-force-push",
        "deny-branches": ["main"],
        "action": "deny",
        "reason": "Force pushing to main is not permitted",
    }
    payload = _bash("git push --force origin main")
    result = evaluate(payload, [deny_rule, rule])
    assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# Integration tests: realistic workflows through the full engine
# ---------------------------------------------------------------------------

def test_allow_python3_inline_analysis(rule):
    """python3 -c for JSON/config inspection → allow."""
    cmd = "python3 -c \"import json; d=json.load(open('package.json')); print(d['version'])\""
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_python3_multiline_heredoc(rule):
    """Multiline python3 via heredoc → allow."""
    cmd = (
        "python3 << 'PYEOF'\n"
        "import os\n"
        "for root, dirs, files in os.walk('src'):\n"
        "    for f in files:\n"
        "        print(os.path.join(root, f))\n"
        "PYEOF"
    )
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_node_inline(rule):
    """node -e for quick package.json inspection → allow."""
    cmd = "node -e \"const p=require('./package.json'); console.log(p.version)\""
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_git_log_analysis_pipeline(rule):
    """git log piped through grep and head → allow."""
    cmd = "git log --all --oneline | grep -i 'migration' | head -20"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_git_for_loop(rule):
    """for loop fetching multiple branches → allow."""
    cmd = "for branch in main develop staging; do\n  git fetch origin $branch\ndone"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_find_xargs_grep(rule):
    """find piped to xargs grep for symbol search → allow."""
    cmd = "find . -name '*.py' -not -path '*/.venv/*' | xargs grep -l 'DeprecatedClass'"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_npm_install_and_build(rule):
    """npm install && npm run build → allow."""
    assert evaluate(_bash("npm install && npm run build"), [rule])["decision"] == "allow"


def test_allow_env_prefix_jest(rule):
    """NODE_ENV=test jest → allow (env var prefix is stripped, jest is safe)."""
    assert evaluate(_bash("NODE_ENV=test jest --coverage"), [rule])["decision"] == "allow"


def test_allow_uv_run_pytest(rule):
    """uv run pytest → allow."""
    assert evaluate(_bash("uv run pytest tests/ -x --tb=short"), [rule])["decision"] == "allow"


def test_allow_timeout_pytest(rule):
    """timeout wrapping pytest → allow."""
    assert evaluate(_bash("timeout 120 pytest tests/integration/ -v"), [rule])["decision"] == "allow"


def test_allow_pytest_tee_tail(rule):
    """pytest output captured via tee and tailed → allow."""
    cmd = "pytest tests/ -v 2>&1 | tee /tmp/test-results.txt | tail -40"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_sed_in_place_rename(rule):
    """sed -i for symbol rename across files → allow."""
    cmd = "sed -i '' 's/OldApiClient/NewApiClient/g' src/**/*.ts"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_curl_jq_pipeline(rule):
    """curl + jq to inspect a REST API response → allow."""
    cmd = "curl -s 'https://api.github.com/repos/org/repo/pulls' | jq '.[].title'"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_source_venv_activate(rule):
    """source .venv/bin/activate before running tests → allow."""
    cmd = "source .venv/bin/activate && python3 -m pytest"
    assert evaluate(_bash(cmd), [rule])["decision"] == "allow"


def test_allow_make_lint_test(rule):
    """make lint && make test → allow."""
    assert evaluate(_bash("make lint && make test"), [rule])["decision"] == "allow"


def test_falls_through_ssh(rule):
    """ssh is in _UNSAFE — not matched by bash-safe, falls through."""
    assert evaluate(_bash("ssh user@host 'cat /etc/passwd'"), [rule])["decision"] == "proceed"


def test_falls_through_dd(rule):
    """dd is in _UNSAFE — not matched by bash-safe, falls through."""
    assert evaluate(_bash("dd if=/dev/urandom of=/tmp/out bs=4M count=1"), [rule])["decision"] == "proceed"


def test_falls_through_eval(rule):
    """eval is in _UNSAFE — not matched by bash-safe, falls through."""
    assert evaluate(_bash("eval \"$(cat script.sh)\""), [rule])["decision"] == "proceed"


def test_falls_through_security(rule):
    """security is in _UNSAFE — not matched by bash-safe, falls through."""
    assert evaluate(_bash("security find-generic-password -s 'myservice' -w"), [rule])["decision"] == "proceed"


def test_unknown_tool_allowed(rule):
    """An unknown tool is allowed in denylist mode — only explicitly unsafe tools are blocked."""
    assert evaluate(_bash("my-custom-internal-tool --run"), [rule])["decision"] == "allow"


def test_rdme_cli_allowed(rule):
    """rdme (readme.com CLI) is allowed — not in denylist."""
    assert evaluate(_bash("result=$(npx rdme docs upload --key=$KEY)"), [rule])["decision"] == "allow"
