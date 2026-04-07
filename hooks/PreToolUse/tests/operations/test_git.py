"""Unit tests for git operation handlers."""

from operations.common import _tokenize
from operations.git import (
    _extract_push_branch,
    _is_force_flag,
    matches_git_force_push,
    matches_git_push_direct,
    matches_git_reset_hard,
)

DENY_MAIN = {"deny-branches": ["main", "master"], "action": "deny"}
ALLOW_FEATURE = {"allow-branches": ["*"], "action": "allow"}
DENY_LOCAL_RESET = {"deny-targets": ["HEAD~*", "HEAD^*", "HEAD@*"], "action": "deny"}
ALLOW_ORIGIN_RESET = {"allow-targets": ["origin/*"], "action": "allow"}
DENY_DIRECT_MAIN = {"deny-branches": ["main", "master"], "action": "deny"}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/repo"}


# ---------------------------------------------------------------------------
# _extract_push_branch
# ---------------------------------------------------------------------------


class TestExtractPushBranch:
    def test_simple(self):
        assert _extract_push_branch(_tokenize("git push origin main")) == "main"

    def test_with_force_flag(self):
        assert _extract_push_branch(_tokenize("git push --force origin main")) == "main"

    def test_with_short_force_flag(self):
        assert _extract_push_branch(_tokenize("git push -f origin feature/foo")) == "feature/foo"

    def test_refspec_colon(self):
        assert _extract_push_branch(_tokenize("git push origin HEAD:main")) == "main"

    def test_refs_heads_prefix(self):
        assert _extract_push_branch(_tokenize("git push origin refs/heads/main")) == "main"

    def test_no_branch_returns_none(self):
        assert _extract_push_branch(_tokenize("git push origin")) is None

    def test_no_remote_returns_none(self):
        assert _extract_push_branch(_tokenize("git push")) is None


# ---------------------------------------------------------------------------
# _is_force_flag
# ---------------------------------------------------------------------------


def test_force_flag_long():
    assert _is_force_flag(_tokenize("git push --force origin main")) is True


def test_force_flag_short():
    assert _is_force_flag(_tokenize("git push -f origin main")) is True


def test_force_with_lease():
    assert _is_force_flag(_tokenize("git push --force-with-lease origin main")) is True


def test_no_force_flag():
    assert _is_force_flag(_tokenize("git push origin main")) is False


# ---------------------------------------------------------------------------
# matches_git_force_push
# ---------------------------------------------------------------------------


class TestMatchesGitForcePush:
    def test_deny_force_push_main(self):
        p = bash("git push --force origin main")
        assert matches_git_force_push(p, DENY_MAIN) is True

    def test_deny_force_push_master(self):
        p = bash("git push -f origin master")
        assert matches_git_force_push(p, DENY_MAIN) is True

    def test_deny_no_match_feature_branch(self):
        p = bash("git push --force origin feature/my-feature")
        assert matches_git_force_push(p, DENY_MAIN) is False

    def test_allow_force_push_any_branch(self):
        p = bash("git push --force origin feature/foo")
        assert matches_git_force_push(p, ALLOW_FEATURE) is True

    def test_allow_does_not_match_non_force(self):
        p = bash("git push origin feature/foo")
        assert matches_git_force_push(p, ALLOW_FEATURE) is False

    def test_non_bash_returns_false(self):
        p = {"tool_name": "Read", "tool_input": {"file_path": "/f"}, "cwd": "/"}
        assert matches_git_force_push(p, DENY_MAIN) is False

    def test_non_git_command_returns_false(self):
        p = bash("hg push --force")
        assert matches_git_force_push(p, DENY_MAIN) is False

    def test_deny_force_push_no_branch_does_not_deny(self):
        # git push --force origin with no explicit branch — can't confirm it's
        # main, so deny rule should NOT match (allow rule with * will catch it)
        p = bash("git push --force origin")
        assert matches_git_force_push(p, DENY_MAIN) is False

    def test_force_with_lease_counts_as_force(self):
        p = bash("git push --force-with-lease origin main")
        assert matches_git_force_push(p, DENY_MAIN) is True


# ---------------------------------------------------------------------------
# matches_git_reset_hard
# ---------------------------------------------------------------------------


class TestMatchesGitResetHard:
    def test_deny_head_tilde(self):
        p = bash("git reset --hard HEAD~1")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is True

    def test_deny_head_caret(self):
        p = bash("git reset --hard HEAD^")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is True

    def test_deny_head_at(self):
        p = bash("git reset --hard HEAD@{2}")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is True

    def test_deny_no_match_origin(self):
        p = bash("git reset --hard origin/main")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is False

    def test_allow_origin_matches(self):
        p = bash("git reset --hard origin/main")
        assert matches_git_reset_hard(p, ALLOW_ORIGIN_RESET) is True

    def test_allow_origin_no_match_local(self):
        p = bash("git reset --hard HEAD~1")
        assert matches_git_reset_hard(p, ALLOW_ORIGIN_RESET) is False

    def test_no_hard_flag_no_match(self):
        p = bash("git reset --soft HEAD~1")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is False

    def test_non_git_command_no_match(self):
        p = bash("svn revert --hard HEAD~1")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is False


# ---------------------------------------------------------------------------
# matches_git_push_direct
# ---------------------------------------------------------------------------


class TestMatchesGitPushDirect:
    def test_direct_push_main_denied(self):
        p = bash("git push origin main")
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is True

    def test_direct_push_master_denied(self):
        p = bash("git push origin master")
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is True

    def test_feature_branch_not_denied(self):
        p = bash("git push origin feature/foo")
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is False

    def test_force_push_not_matched_by_direct_rule(self):
        # Force pushes are handled by git-force-push, not git-push-direct
        p = bash("git push --force origin main")
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is False

    def test_non_bash_no_match(self):
        p = {"tool_name": "Read", "tool_input": {}, "cwd": "/"}
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is False


# ---------------------------------------------------------------------------
# Compound command splitting
# ---------------------------------------------------------------------------


class TestCompoundCommands:
    """Verify that sensitive git operations in compound commands are caught."""

    def test_force_push_after_and_and(self):
        p = bash("git fetch && git push --force origin main")
        assert matches_git_force_push(p, DENY_MAIN) is True

    def test_force_push_after_semicolon(self):
        p = bash("git stash; git push -f origin master")
        assert matches_git_force_push(p, DENY_MAIN) is True

    def test_reset_hard_after_and_and(self):
        p = bash("git fetch && git reset --hard HEAD~1")
        assert matches_git_reset_hard(p, DENY_LOCAL_RESET) is True

    def test_push_direct_after_and_and(self):
        p = bash("git add . && git commit -m 'x' && git push origin main")
        assert matches_git_push_direct(p, DENY_DIRECT_MAIN) is True

    def test_safe_compound_no_match(self):
        p = bash("git fetch && git status")
        assert matches_git_force_push(p, DENY_MAIN) is False
