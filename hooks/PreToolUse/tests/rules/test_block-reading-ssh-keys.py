"""Tests for rule: Block reading SSH keys."""

from pathlib import Path

from engine import evaluate

HOME = str(Path.home())
REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block reading SSH keys"
RULE_ID = "block-ssh-reads"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Read tool on ~/.ssh/id_rsa is denied."""
    payload = _payload("Read", {"file_path": f"{HOME}/.ssh/id_rsa"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"
    assert "SSH" in result["reason"]


def test_no_match(rule):
    """Read tool on a regular project file is not denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_bash_cat(rule):
    """cat ~/.ssh/id_rsa via Bash is also denied."""
    payload = _payload("Bash", {"command": f"cat {HOME}/.ssh/id_rsa"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_known_hosts(rule):
    """Reads to ~/.ssh/known_hosts are also denied."""
    payload = _payload("Read", {"file_path": f"{HOME}/.ssh/known_hosts"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_file_outside_ssh_dir_allowed(rule):
    """Reading ~/.ssh itself (the dir) or non-SSH files is not matched by the wildcard."""
    # ~/.ssh/ directory listing via cat of a non-ssh-dir file
    payload = _payload("Read", {"file_path": f"{HOME}/.config/something"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
