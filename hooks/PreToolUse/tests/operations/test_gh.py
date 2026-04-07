"""Unit tests for GitHub CLI operation handlers."""

from operations.gh import matches_gh_api, matches_gh_pr_merge

DENY_MERGE_MAIN = {"deny-base-branches": ["main", "master"], "action": "deny"}
DENY_DELETE_METHOD = {"deny-methods": ["DELETE"], "action": "deny"}
DENY_URL_PATTERN = {"deny-patterns": [r"/repos/.+/actions/"], "action": "deny"}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/repo"}


# ---------------------------------------------------------------------------
# matches_gh_pr_merge
# ---------------------------------------------------------------------------


class TestMatchesGhPrMerge:
    def test_merge_with_base_main(self):
        p = bash("gh pr merge 42 --base main --merge")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is True

    def test_merge_with_base_master(self):
        p = bash("gh pr merge 42 -B master --squash")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is True

    def test_merge_with_base_feature_not_denied(self):
        p = bash("gh pr merge 42 --base release/v2 --merge")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is False

    def test_merge_no_base_flag_denied_conservatively(self):
        # No --base flag → could be merging into main, apply deny
        p = bash("gh pr merge 42 --squash")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is True

    def test_non_bash_returns_false(self):
        p = {"tool_name": "Read", "tool_input": {}, "cwd": "/"}
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is False

    def test_gh_pr_list_not_matched(self):
        p = bash("gh pr list")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is False

    def test_gh_pr_view_not_matched(self):
        p = bash("gh pr view 42")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is False

    def test_boundary_base_flag_equals_form(self):
        p = bash("gh pr merge 42 --base=main")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is True


# ---------------------------------------------------------------------------
# matches_gh_api
# ---------------------------------------------------------------------------


class TestMatchesGhApi:
    def test_delete_method_denied(self):
        p = bash("gh api --method DELETE /repos/org/repo/issues/1")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is True

    def test_delete_method_short_flag(self):
        p = bash("gh api -X DELETE /repos/org/repo/issues/1")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is True

    def test_get_method_not_denied(self):
        p = bash("gh api --method GET /repos/org/repo/issues")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is False

    def test_post_method_not_denied_by_delete_rule(self):
        p = bash("gh api --method POST /repos/org/repo/issues -f title=Foo")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is False

    def test_url_pattern_denied(self):
        p = bash("gh api /repos/org/repo/actions/runs")
        assert matches_gh_api(p, DENY_URL_PATTERN) is True

    def test_url_pattern_no_match(self):
        p = bash("gh api /repos/org/repo/pulls")
        assert matches_gh_api(p, DENY_URL_PATTERN) is False

    def test_non_bash_returns_false(self):
        p = {"tool_name": "Read", "tool_input": {}, "cwd": "/"}
        assert matches_gh_api(p, DENY_DELETE_METHOD) is False

    def test_gh_pr_create_not_matched(self):
        p = bash("gh pr create --title Foo")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is False

    def test_boundary_method_case_insensitive(self):
        p = bash("gh api --method delete /repos/org/repo/issues/1")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is True


# ---------------------------------------------------------------------------
# Compound command splitting
# ---------------------------------------------------------------------------


class TestCompoundCommands:
    """Verify that sensitive gh operations in compound commands are caught."""

    def test_pr_merge_after_and_and(self):
        p = bash("gh pr view 42 && gh pr merge 42 --squash")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is True

    def test_api_delete_after_semicolon(self):
        p = bash("gh pr list; gh api --method DELETE /repos/org/repo/issues/1")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is True

    def test_api_delete_after_and_and(self):
        p = bash("echo ok && gh api -X DELETE /repos/org/repo/issues/1")
        assert matches_gh_api(p, DENY_DELETE_METHOD) is True

    def test_safe_compound_no_match(self):
        p = bash("gh pr list && gh pr view 42")
        assert matches_gh_pr_merge(p, DENY_MERGE_MAIN) is False
