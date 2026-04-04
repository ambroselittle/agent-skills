"""Tests for rule: Allow writes to .claude/ inside a repo."""

from engine import evaluate

RULE_DESCRIPTION = "Allow writes to .claude/ inside a repo"

REPO = "/repo/myproject"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Write tool to .claude/settings.json inside a repo is allowed."""
    payload = _payload("Write", {"file_path": f"{REPO}/.claude/settings.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "allow"


def test_no_match(rule):
    """Write tool to a regular file outside .claude/ is not matched."""
    payload = _payload("Write", {"file_path": f"{REPO}/src/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_edit_tool(rule):
    """Edit tool to .claude/rules/custom.md is also allowed."""
    payload = _payload("Edit", {"file_path": f"{REPO}/.claude/rules/custom.md"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "allow"


def test_boundary_nested_path(rule):
    """Write to a deeply nested .claude path is allowed."""
    payload = _payload("Write", {"file_path": f"{REPO}/.claude/hooks/pre-tool-use/rules.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "allow"


def test_boundary_read_not_matched(rule):
    """Read tool on .claude/ is not matched — this is a write-path rule."""
    payload = _payload("Read", {"file_path": f"{REPO}/.claude/settings.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
