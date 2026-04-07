"""Tests for rule: Block direct push to main or master."""

from unittest.mock import patch

from engine import evaluate

RULE_DESCRIPTION = "Block direct push to main or master — these require a PR"
RULE_ID = "block-push-main"


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


def test_boundary_initial_push_to_empty_remote_allowed(rule):
    """Initial push to an empty remote (new repo) is allowed — nothing to protect."""
    with patch("operations.git._remote_is_empty", return_value=True):
        result = evaluate(_payload("git push -u origin main"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_cd_path_used_for_empty_remote_check(rule):
    """cd /path && git push uses the cd path as cwd when checking if remote is empty."""
    captured_cwd = []

    def mock_is_empty(remote, cwd):
        captured_cwd.append(cwd)
        return True

    with patch("operations.git._remote_is_empty", side_effect=mock_is_empty):
        result = evaluate(_payload("cd /some/repo && git push -u origin main"), [rule])

    assert result["decision"] == "proceed"
    assert captured_cwd == ["/some/repo"]


def test_boundary_non_empty_remote_still_denied(rule):
    """Push to main on a non-empty remote is still denied."""
    with patch("operations.git._remote_is_empty", return_value=False):
        result = evaluate(_payload("git push origin main"), [rule])
    assert result["decision"] == "deny"
