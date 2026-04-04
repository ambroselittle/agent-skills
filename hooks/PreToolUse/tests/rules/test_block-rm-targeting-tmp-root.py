"""Tests for rule: Block rm targeting /tmp root.

The rule blocks `rm` commands that target /tmp itself or glob all of /tmp,
while allowing `rm` against a specific subdirectory under /tmp.

Blocked:   rm -rf /tmp          (bare /tmp)
           rm -rf /tmp/         (trailing slash — still /tmp root)
           rm -rf /tmp/*        (glob — nukes everything in /tmp)
Allowed:   rm -rf /tmp/my-dir   (specific subdirectory — safe to allow)
"""

from engine import evaluate

RULE_DESCRIPTION = "Block rm targeting /tmp root — removing the entire temp directory is likely unintended; specify a subdirectory"
RULE_ID = "block-rm-tmp"


def _bash(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


# ---------------------------------------------------------------------------
# Must-block cases
# ---------------------------------------------------------------------------


def test_match(rule):
    """rm -rf /tmp is denied — targets the temp directory root."""
    result = evaluate(_bash("rm -rf /tmp"), [rule])
    assert result["decision"] == "deny"


def test_match_trailing_slash(rule):
    """rm -rf /tmp/ is denied — trailing slash still targets /tmp root."""
    result = evaluate(_bash("rm -rf /tmp/"), [rule])
    assert result["decision"] == "deny"


def test_match_glob(rule):
    """rm -rf /tmp/* is denied — glob removes everything inside /tmp."""
    result = evaluate(_bash("rm -rf /tmp/*"), [rule])
    assert result["decision"] == "deny"


# ---------------------------------------------------------------------------
# Must-allow cases (specific subdirectory — falls through to Claude's rules)
# ---------------------------------------------------------------------------


def test_no_match(rule):
    """rm -rf /tmp/my-dir falls through — targets a specific subdirectory, not /tmp root."""
    result = evaluate(_bash("rm -rf /tmp/my-dir"), [rule])
    assert result["decision"] == "proceed"


def test_no_match_numbered_subdir(rule):
    """rm -rf /tmp/hook-test-probe-123 falls through — specific subdir with numbers."""
    result = evaluate(_bash("rm -rf /tmp/hook-test-probe-123"), [rule])
    assert result["decision"] == "proceed"


def test_no_match_nested_subdir(rule):
    """rm -rf /tmp/some-build/dist falls through — nested path under /tmp."""
    result = evaluate(_bash("rm -rf /tmp/some-build/dist"), [rule])
    assert result["decision"] == "proceed"


def test_no_match_subdir_contents(rule):
    """rm -rf /tmp/my-dir/* falls through — cleaning up contents of a specific subdir is fine."""
    result = evaluate(_bash("rm -rf /tmp/my-dir/*"), [rule])
    assert result["decision"] == "proceed"


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_boundary_fr_flag_order(rule):
    """rm -fr /tmp is denied — flag order variation (-fr instead of -rf)."""
    result = evaluate(_bash("rm -fr /tmp"), [rule])
    assert result["decision"] == "deny"


def test_boundary_r_flag_only(rule):
    """rm -r /tmp is denied — -r alone is still recursive removal of /tmp."""
    result = evaluate(_bash("rm -r /tmp"), [rule])
    assert result["decision"] == "deny"


def test_boundary_non_recursive(rule):
    """rm /tmp is denied — even non-recursive rm on /tmp root is blocked."""
    result = evaluate(_bash("rm /tmp"), [rule])
    assert result["decision"] == "deny"


def test_boundary_chained_after_and(rule):
    """rm -rf /tmp && echo done is denied — chaining doesn't bypass the block."""
    result = evaluate(_bash("rm -rf /tmp && echo done"), [rule])
    assert result["decision"] == "deny"


def test_boundary_tmpfiles_not_blocked(rule):
    """/tmpfiles is a different path and must not be blocked.

    The pattern matches /tmp followed by end-of-token, not /tmp as a prefix
    of an arbitrary path. /tmpfiles has no separator after /tmp.
    """
    result = evaluate(_bash("rm -rf /tmpfiles"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_other_absolute_path_not_blocked(rule):
    """rm -rf /var/tmp/build falls through — /var/tmp is not /tmp."""
    result = evaluate(_bash("rm -rf /var/tmp/build"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_glob_inside_subdir_not_blocked(rule):
    """rm -rf /tmp/my-build/* falls through — glob inside a specific subdir is allowed.

    This is a common cleanup pattern: remove the contents of your own build
    dir without removing the dir itself. /tmp root is not targeted.
    """
    result = evaluate(_bash("rm -rf /tmp/my-build/*"), [rule])
    assert result["decision"] == "proceed"
