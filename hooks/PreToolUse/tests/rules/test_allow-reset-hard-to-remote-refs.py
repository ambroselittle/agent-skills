"""Tests for rule: Allow reset hard to remote refs."""

from engine import evaluate

RULE_DESCRIPTION = "Allow reset hard to remote refs — approved workflow for syncing local to origin"
RULE_ID = "allow-reset-hard-remote"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """git reset --hard origin/main matches the allow rule."""
    result = evaluate(_payload("git reset --hard origin/main"), [rule])
    assert result["decision"] == "allow"


def test_no_match(rule):
    """git reset --hard HEAD~1 does not match this allow rule."""
    result = evaluate(_payload("git reset --hard HEAD~1"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_any_origin_branch(rule):
    """origin/* matches any remote branch, not just main."""
    result = evaluate(_payload("git reset --hard origin/feature/foo"), [rule])
    assert result["decision"] == "allow"


def test_boundary_no_hard_flag_not_matched(rule):
    """git reset --soft origin/main is not a hard reset."""
    result = evaluate(_payload("git reset --soft origin/main"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_deny_beats_allow_for_local_ref(rule):
    """
    When both this allow rule and a deny rule for local refs are present,
    a local ref target: deny wins.
    """
    deny_local = {
        "description": "Block reset hard to local refs",
        "operation": "git-reset-hard",
        "deny-targets": ["HEAD~*", "HEAD^*", "HEAD@*"],
        "action": "deny",
        "reason": "Rewinding local commits can cause data loss",
    }
    result = evaluate(_payload("git reset --hard HEAD~2"), [rule, deny_local])
    assert result["decision"] == "deny"
