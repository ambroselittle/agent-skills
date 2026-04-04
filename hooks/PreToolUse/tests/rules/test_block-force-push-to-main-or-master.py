"""Tests for rule: Block force push to main or master."""

from engine import evaluate

RULE_DESCRIPTION = "Block force push to main or master"
RULE_ID = "block-force-push-main"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """git push --force origin main is denied."""
    result = evaluate(_payload("git push --force origin main"), [rule])
    assert result["decision"] == "deny"
    assert "PR" in result["reason"]


def test_no_match(rule):
    """git push --force to a feature branch is not denied by this rule."""
    result = evaluate(_payload("git push --force origin feature/my-feature"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_short_force_flag(rule):
    """git push -f origin master is also denied."""
    result = evaluate(_payload("git push -f origin master"), [rule])
    assert result["decision"] == "deny"


def test_boundary_force_with_lease(rule):
    """git push --force-with-lease to main is denied."""
    result = evaluate(_payload("git push --force-with-lease origin main"), [rule])
    assert result["decision"] == "deny"


def test_boundary_refspec_colon_form(rule):
    """git push --force origin HEAD:main is denied."""
    result = evaluate(_payload("git push --force origin HEAD:main"), [rule])
    assert result["decision"] == "deny"


def test_boundary_non_force_push_not_matched(rule):
    """Regular git push to main is not matched by the force-push rule."""
    result = evaluate(_payload("git push origin main"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_no_branch_not_denied(rule):
    """Force push with no explicit branch should NOT be denied — we can't
    confirm it targets main, so don't assume the worst."""
    result = evaluate(_payload("git push --force-with-lease"), [rule])
    assert result["decision"] == "proceed"
