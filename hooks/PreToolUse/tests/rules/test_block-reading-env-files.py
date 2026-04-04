"""Tests for rule: Block reading .env files."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block reading .env files — apply even inside repos since they may contain secrets"
RULE_ID = "block-env-reads"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Read tool on repo-root .env is denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/.env"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_no_match(rule):
    """Read tool on a non-env file is not denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_nested_env_file(rule):
    """.env in a subdirectory is also denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/src/services/.env"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_env_local(rule):
    """.env.local is denied (matches **/.env.*)."""
    payload = _payload("Read", {"file_path": f"{REPO}/.env.local"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_env_test(rule):
    """.env.test is denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/.env.test"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_envrc(rule):
    """.envrc is denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/src/.envrc"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_outside_repo_not_blocked(rule):
    """
    .env files outside the repo root are NOT blocked by the unanchored pattern.
    This is by design — the unanchored pattern is repo-relative.
    """
    payload = _payload("Read", {"file_path": "/other/project/.env"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_bash_cat(rule):
    """cat of .env file via Bash is denied."""
    payload = _payload("Bash", {"command": f"cat {REPO}/.env"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"
