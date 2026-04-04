"""Tests for rule: Allow force push to feature branches (e.g. after rebase)."""

from engine import evaluate

RULE_DESCRIPTION = "Allow force push to feature branches (e.g. after rebase)"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """Force push to a feature branch matches the allow rule."""
    result = evaluate(_payload("git push --force origin feature/my-feature"), [rule])
    assert result["decision"] == "allow"


def test_no_match(rule):
    """A non-force push does not match this rule."""
    result = evaluate(_payload("git push origin feature/my-feature"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_wildcard_matches_any_branch(rule):
    """allow-branches: ['*'] matches all branch names."""
    result = evaluate(_payload("git push -f origin alittle/some-branch"), [rule])
    assert result["decision"] == "allow"


def test_boundary_no_branch_allowed_by_wildcard(rule):
    """Force push with no explicit branch is allowed when allow-branches
    has wildcard — covers the common tracking-branch push workflow."""
    result = evaluate(_payload("git push --force-with-lease"), [rule])
    assert result["decision"] == "allow"


def test_boundary_no_branch_with_deny_and_allow():
    """When both deny (main) and allow (*) rules exist, force push with
    no explicit branch should be allowed — deny can't confirm it's main,
    allow's wildcard covers any branch."""
    deny_main = {
        "description": "Block force push to main or master",
        "operation": "git-force-push",
        "deny-branches": ["main", "master"],
        "action": "deny",
        "reason": "Force pushing to main/master is not permitted",
    }
    allow_all = {
        "description": "Allow force push to feature branches",
        "operation": "git-force-push",
        "allow-branches": ["*"],
        "action": "allow",
    }
    result = evaluate(_payload("git push --force-with-lease"), [deny_main, allow_all])
    assert result["decision"] == "allow"


def test_boundary_deny_wins_over_allow(rule):
    """
    When both a deny rule (for main) and this allow rule match,
    deny takes priority. This verifies the deny-wins model.
    """
    deny_main = {
        "description": "Block force push to main or master",
        "operation": "git-force-push",
        "deny-branches": ["main", "master"],
        "action": "deny",
        "reason": "Force pushing to main/master is not permitted",
    }
    # Force push to main: both rules apply — deny must win
    result = evaluate(_payload("git push --force origin main"), [rule, deny_main])
    assert result["decision"] == "deny"
