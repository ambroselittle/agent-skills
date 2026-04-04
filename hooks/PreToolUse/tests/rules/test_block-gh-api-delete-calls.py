"""Tests for rule: Block gh api DELETE calls."""

from engine import evaluate

RULE_DESCRIPTION = "Block gh api DELETE calls — these are irreversible"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """gh api --method DELETE is denied."""
    result = evaluate(_payload("gh api --method DELETE /repos/org/repo/issues/1"), [rule])
    assert result["decision"] == "deny"


def test_no_match(rule):
    """gh api GET is not denied."""
    result = evaluate(_payload("gh api /repos/org/repo/issues"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_short_method_flag(rule):
    """gh api -X DELETE is also denied."""
    result = evaluate(_payload("gh api -X DELETE /repos/org/repo/labels/1"), [rule])
    assert result["decision"] == "deny"


def test_boundary_post_not_denied(rule):
    """POST requests are not covered by this rule."""
    result = evaluate(_payload("gh api --method POST /repos/org/repo/issues -f title=Bug"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_method_case_insensitive(rule):
    """Method matching is case-insensitive."""
    result = evaluate(_payload("gh api --method delete /repos/org/repo/issues/1"), [rule])
    assert result["decision"] == "deny"


def test_boundary_non_api_command_not_matched(rule):
    """gh pr create is not an api command."""
    result = evaluate(_payload("gh pr create --title Foo"), [rule])
    assert result["decision"] == "proceed"
