"""Tests for rule: Allow writes to ~/.agent-skills/ — shared cache and state for agent skills."""

from pathlib import Path

from engine import evaluate

RULE_DESCRIPTION = "Allow writes to ~/.agent-skills/ — shared cache and state for agent skills"
RULE_ID = "allow-write-agent-skills"

REPO = "/repo/myproject"
HOME = str(Path.home())


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Write tool to ~/.agent-skills/.version-cache/ is allowed."""
    payload = _payload(
        "Write", {"file_path": f"{HOME}/.agent-skills/.version-cache/fullstack-ts.json"}
    )
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "allow"


def test_no_match(rule):
    """Write tool to a regular file outside ~/.agent-skills/ is not matched."""
    payload = _payload("Write", {"file_path": f"{REPO}/src/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_nested_path(rule):
    """Write to a deeply nested path under ~/.agent-skills/ is allowed."""
    payload = _payload("Write", {"file_path": f"{HOME}/.agent-skills/some/deep/nested/file.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "allow"


def test_boundary_read_not_matched(rule):
    """Read tool on ~/.agent-skills/ is not matched — this is a write-path rule."""
    payload = _payload(
        "Read", {"file_path": f"{HOME}/.agent-skills/.version-cache/fullstack-ts.json"}
    )
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
