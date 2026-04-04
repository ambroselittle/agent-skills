"""Tests for rule: Block reset hard to local refs."""

from engine import evaluate

RULE_DESCRIPTION = "Block reset hard to local refs — rewrites or discards local commit history"
RULE_ID = "block-reset-hard-local"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """git reset --hard HEAD~1 is denied."""
    result = evaluate(_payload("git reset --hard HEAD~1"), [rule])
    assert result["decision"] == "deny"
    assert "data loss" in result["reason"]


def test_no_match(rule):
    """git reset --hard origin/main is not denied (remote ref)."""
    result = evaluate(_payload("git reset --hard origin/main"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_head_caret(rule):
    """git reset --hard HEAD^ (parent) is denied."""
    result = evaluate(_payload("git reset --hard HEAD^"), [rule])
    assert result["decision"] == "deny"


def test_boundary_head_at_reflog(rule):
    """git reset --hard HEAD@{1} (reflog) is denied."""
    result = evaluate(_payload("git reset --hard HEAD@{1}"), [rule])
    assert result["decision"] == "deny"


def test_boundary_head_tilde_many(rule):
    """git reset --hard HEAD~5 is denied."""
    result = evaluate(_payload("git reset --hard HEAD~5"), [rule])
    assert result["decision"] == "deny"


def test_boundary_soft_reset_not_matched(rule):
    """git reset --soft HEAD~1 is not a hard reset — not matched."""
    result = evaluate(_payload("git reset --soft HEAD~1"), [rule])
    assert result["decision"] == "proceed"
