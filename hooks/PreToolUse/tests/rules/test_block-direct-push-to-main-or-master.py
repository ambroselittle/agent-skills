"""Tests for rule: Block direct push to main or master."""

from engine import evaluate

RULE_DESCRIPTION = "Block direct push to main or master — these require a PR"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """git push origin main is denied."""
    result = evaluate(_payload("git push origin main"), [rule])
    assert result["decision"] == "deny"
    assert "PR" in result["reason"]


def test_no_match(rule):
    """git push to a feature branch is not denied."""
    result = evaluate(_payload("git push origin feature/my-feature"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_master_denied(rule):
    """git push origin master is also denied."""
    result = evaluate(_payload("git push origin master"), [rule])
    assert result["decision"] == "deny"


def test_boundary_force_push_not_matched(rule):
    """
    Force pushes to main are NOT matched by git-push-direct.
    They are handled by the git-force-push rule instead.
    """
    result = evaluate(_payload("git push --force origin main"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_push_with_set_upstream(rule):
    """git push -u origin main is a direct push — denied."""
    result = evaluate(_payload("git push -u origin main"), [rule])
    assert result["decision"] == "deny"
