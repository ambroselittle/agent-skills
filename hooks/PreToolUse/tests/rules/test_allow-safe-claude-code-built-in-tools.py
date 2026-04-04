"""Tests for rule: Allow safe Claude Code built-in tools."""

from engine import evaluate

RULE_DESCRIPTION = "Allow safe Claude Code built-in tools"


def _tool(name, cwd="/repo"):
    return {"tool_name": name, "tool_input": {}, "cwd": cwd}


def test_match(rule):
    """Read tool is allowed."""
    assert evaluate(_tool("Read"), [rule])["decision"] == "allow"


def test_no_match(rule):
    """Bash is not in the list — handled by bash-safe separately."""
    assert evaluate(_tool("Bash"), [rule])["decision"] == "proceed"


def test_boundary_write(rule):
    assert evaluate(_tool("Write"), [rule])["decision"] == "allow"


def test_boundary_task_tools(rule):
    for name in ("TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop", "TaskUpdate"):
        assert evaluate(_tool(name), [rule])["decision"] == "allow", f"{name} should be allowed"


def test_boundary_workflow_tools(rule):
    for name in ("EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree"):
        assert evaluate(_tool(name), [rule])["decision"] == "allow", f"{name} should be allowed"


def test_boundary_meta_tools(rule):
    for name in ("ToolSearch", "ListMcpResourcesTool", "ReadMcpResourceTool", "LSP", "AskUserQuestion", "TodoWrite"):
        assert evaluate(_tool(name), [rule])["decision"] == "allow", f"{name} should be allowed"


def test_boundary_mcp_tool_not_matched(rule):
    """MCP tools have their own rule — not covered here."""
    assert evaluate(_tool("mcp__linear__save_issue"), [rule])["decision"] == "proceed"


def test_boundary_unknown_tool_not_matched(rule):
    assert evaluate(_tool("SomeFutureTool"), [rule])["decision"] == "proceed"
