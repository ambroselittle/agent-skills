"""Tests for rule: Block repo deletion via gh."""

from engine import evaluate

RULE_DESCRIPTION = "Block repo deletion via gh"
RULE_ID = "block-gh-repo-delete"


def _payload(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """gh repo delete is denied."""
    result = evaluate(_payload("gh repo delete my-org/my-repo"), [rule])
    assert result["decision"] == "deny"


def test_no_match(rule):
    """gh repo list is not denied."""
    result = evaluate(_payload("gh repo list"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_with_yes_flag(rule):
    """gh repo delete --yes is also denied."""
    result = evaluate(_payload("gh repo delete my-org/my-repo --yes"), [rule])
    assert result["decision"] == "deny"


def test_boundary_repo_view_not_matched(rule):
    """gh repo view is not matched."""
    result = evaluate(_payload("gh repo view my-org/my-repo"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_non_bash_not_matched(rule):
    """Pattern rules match Bash commands, not Read tool file paths."""
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "/repo/scripts/deploy.sh"},
        "cwd": "/repo",
    }
    result = evaluate(payload, [rule])
    assert result["decision"] == "proceed"
