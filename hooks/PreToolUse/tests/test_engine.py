"""Tests for the rule evaluation engine (deny-wins priority, pattern matching, etc.)."""

from engine import _match_pattern, evaluate

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def bash(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def read_tool(path, cwd="/repo"):
    return {"tool_name": "Read", "tool_input": {"file_path": path}, "cwd": cwd}


# ---------------------------------------------------------------------------
# Priority: deny > ask > allow
# ---------------------------------------------------------------------------

ALLOW_RULE = {
    "description": "allow all bash",
    "operation": None,
    "pattern": ".*",
    "action": "allow",
}
ASK_RULE = {"description": "ask all bash", "operation": None, "pattern": ".*", "action": "ask"}
DENY_RULE = {
    "description": "deny all bash",
    "operation": None,
    "pattern": ".*",
    "action": "deny",
    "reason": "denied",
}


def test_deny_beats_allow():
    payload = bash("echo hi")
    result = evaluate(payload, [ALLOW_RULE, DENY_RULE])
    assert result["decision"] == "deny"


def test_deny_beats_ask():
    payload = bash("echo hi")
    result = evaluate(payload, [ASK_RULE, DENY_RULE])
    assert result["decision"] == "deny"


def test_ask_beats_allow():
    payload = bash("echo hi")
    result = evaluate(payload, [ALLOW_RULE, ASK_RULE])
    assert result["decision"] == "ask"


def test_allow_when_no_deny_or_ask():
    payload = bash("echo hi")
    result = evaluate(payload, [ALLOW_RULE])
    assert result["decision"] == "allow"


def test_proceed_when_no_rules_match():
    payload = bash("echo hi")
    # Pattern that doesn't match
    rule = {"description": "x", "pattern": "^never$", "action": "deny", "reason": "x"}
    result = evaluate(payload, [rule])
    assert result["decision"] == "proceed"


def test_proceed_on_empty_rules():
    result = evaluate(bash("echo hi"), [])
    assert result["decision"] == "proceed"


# ---------------------------------------------------------------------------
# Deny reason is passed through
# ---------------------------------------------------------------------------


def test_deny_includes_reason():
    rule = {
        "description": "x",
        "pattern": "dangerous",
        "action": "deny",
        "reason": "it is dangerous",
    }
    result = evaluate(bash("dangerous command"), [rule])
    assert result["decision"] == "deny"
    assert result["reason"] == "it is dangerous"


def test_allow_has_no_reason():
    rule = {"description": "x", "pattern": ".*", "action": "allow"}
    result = evaluate(bash("echo hi"), [rule])
    assert result["decision"] == "allow"
    assert "reason" not in result


# ---------------------------------------------------------------------------
# All rules evaluated — not just first match
# ---------------------------------------------------------------------------


def test_all_rules_evaluated_deny_wins_even_if_not_first():
    allow_first = {"description": "allow", "pattern": "git", "action": "allow"}
    deny_later = {"description": "deny", "pattern": "force", "action": "deny", "reason": "no force"}
    result = evaluate(bash("git push --force"), [allow_first, deny_later])
    assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# _match_pattern: Bash command matching
# ---------------------------------------------------------------------------


def test_pattern_matches_bash_command():
    assert _match_pattern(bash("gh repo delete my-repo"), "gh repo delete") is True


def test_pattern_no_match_bash_command():
    assert _match_pattern(bash("gh repo list"), "gh repo delete") is False


def test_pattern_matches_read_tool_path():
    payload = read_tool("/home/user/.env")
    assert _match_pattern(payload, r"\.env$") is True


def test_pattern_no_match_read_tool_path():
    payload = read_tool("/home/user/main.py")
    assert _match_pattern(payload, r"\.env$") is False


def test_pattern_non_bash_non_read_returns_false():
    payload = {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}, "cwd": "/repo"}
    assert _match_pattern(payload, ".*") is False


# ---------------------------------------------------------------------------
# Unknown operation is ignored (no crash)
# ---------------------------------------------------------------------------


def test_unknown_operation_ignored():
    rule = {"description": "x", "operation": "nonexistent-op", "action": "deny", "reason": "x"}
    result = evaluate(bash("echo hi"), [rule])
    assert result["decision"] == "proceed"
