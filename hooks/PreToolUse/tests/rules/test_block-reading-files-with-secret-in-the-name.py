"""Tests for rule: Block reading files with secret in the name."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block reading files with secret in the name — likely credentials"
RULE_ID = "block-secret-file-reads"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Read tool on a secrets file is denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/config/secrets.yaml"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_no_match(rule):
    """Read tool on an unrelated file is not denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_secret_as_substring(rule):
    """'secret' anywhere in the file name is denied (e.g. client-secret.json)."""
    payload = _payload("Read", {"file_path": f"{REPO}/auth/client-secret.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_capitalized_secret(rule):
    """Capitalized 'Secret' in the file name is denied (e.g. ClientSecret.json)."""
    payload = _payload("Read", {"file_path": f"{REPO}/auth/ClientSecret.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_uppercase_secret(rule):
    """All-caps 'SECRET' in the file name is denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/PROD_SECRETS.txt"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_mixed_case_secret(rule):
    """Arbitrary casing is denied — path matching is case-insensitive by default."""
    payload = _payload("Read", {"file_path": f"{REPO}/SeCrEtS.txt"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_outside_repo_blocked(rule):
    """Secret files OUTSIDE the repo are also denied — the pattern is filesystem-anchored."""
    payload = _payload("Read", {"file_path": "/Users/someone/Documents/secrets.txt"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_secret_directory_not_blocked(rule):
    """A file INSIDE a secrets/ directory is not blocked unless its own name matches."""
    payload = _payload("Read", {"file_path": f"{REPO}/secrets/readme.md"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_bash_cat(rule):
    """cat of a secret file via Bash is denied."""
    payload = _payload("Bash", {"command": f"cat {REPO}/k8s/api-secret.yaml"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_bash_grep(rule):
    """grep over a secret file via Bash is denied."""
    payload = _payload("Bash", {"command": f"grep -i token {REPO}/secrets.env"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"
