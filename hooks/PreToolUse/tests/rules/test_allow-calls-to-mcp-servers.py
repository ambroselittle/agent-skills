"""Tests for rule: Allow calls to MCP servers."""

from engine import evaluate

RULE_DESCRIPTION = "Allow calls to MCP servers"
RULE_ID = "allow-mcp"


def _mcp(tool_name):
    return {"tool_name": tool_name, "tool_input": {}, "cwd": "/repo"}


def _bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/repo"}


def test_match(rule):
    """An MCP tool call is allowed."""
    result = evaluate(_mcp("mcp__context7__query-docs"), [rule])
    assert result["decision"] == "allow"


def test_no_match(rule):
    """A non-MCP tool call is not matched."""
    result = evaluate(_bash("git status"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_enterprise_mcp(rule):
    """Enterprise MCP servers (claude_ai_ prefix) are also allowed."""
    result = evaluate(_mcp("mcp__claude_ai_Linear__save_issue"), [rule])
    assert result["decision"] == "allow"


def test_boundary_non_mcp_tool(rule):
    """Read tool is not an MCP call — rule does not match."""
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/repo/main.py"}, "cwd": "/repo"}
    result = evaluate(payload, [rule])
    assert result["decision"] == "proceed"
