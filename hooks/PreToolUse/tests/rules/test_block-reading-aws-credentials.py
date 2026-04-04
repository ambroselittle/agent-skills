"""Tests for rule: Block reading AWS credentials."""
from pathlib import Path


from engine import evaluate

HOME = str(Path.home())
REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block reading AWS credentials"
RULE_ID = "block-aws-reads"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Read tool on ~/.aws/credentials is denied."""
    payload = _payload("Read", {"file_path": f"{HOME}/.aws/credentials"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_no_match(rule):
    """Read tool on a regular file is not denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/config.yaml"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_aws_config_file(rule):
    """~/.aws/config is also denied."""
    payload = _payload("Read", {"file_path": f"{HOME}/.aws/config"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_bash_cat(rule):
    """cat ~/.aws/credentials via Bash is denied."""
    payload = _payload("Bash", {"command": f"cat {HOME}/.aws/credentials"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_other_aws_files_not_blocked(rule):
    """Other files under ~/.aws/ (not credentials or config) are not blocked."""
    payload = _payload("Read", {"file_path": f"{HOME}/.aws/cli/cache/token.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
