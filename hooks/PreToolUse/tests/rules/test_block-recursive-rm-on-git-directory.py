"""Tests for rule: Block recursive rm on .git directory."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block recursive rm on .git directory — would destroy repository history"
RULE_ID = "block-rm-git"


def _payload(command, cwd=REPO):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """rm -rf .git is denied."""
    result = evaluate(_payload("rm -rf .git"), [rule])
    assert result["decision"] == "deny"


def test_no_match(rule):
    """rm -rf build/ falls through — .git not involved."""
    result = evaluate(_payload("rm -rf build/"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_trailing_slash(rule):
    """rm -rf .git/ is denied."""
    result = evaluate(_payload("rm -rf .git/"), [rule])
    assert result["decision"] == "deny"


def test_boundary_r_flag_only(rule):
    """rm -r .git is denied — -r alone is also recursive."""
    result = evaluate(_payload("rm -r .git"), [rule])
    assert result["decision"] == "deny"


def test_boundary_fr_flag_order(rule):
    """rm -fr .git is denied — flags in reverse order."""
    result = evaluate(_payload("rm -fr .git"), [rule])
    assert result["decision"] == "deny"


def test_boundary_nested_repo(rule):
    """rm -rf project/.git is denied — nested repo deletion."""
    result = evaluate(_payload("rm -rf project/.git"), [rule])
    assert result["decision"] == "deny"


def test_boundary_nested_repo_trailing_slash(rule):
    """rm -rf project/.git/ is denied."""
    result = evaluate(_payload("rm -rf project/.git/"), [rule])
    assert result["decision"] == "deny"


def test_boundary_file_inside_git_not_blocked(rule):
    """rm .git/MERGE_HEAD falls through — no recursive flag, targets a file inside .git.

    Removing specific files inside .git is a valid recovery operation
    (e.g. clearing a stuck merge state). Only recursive removal of the
    directory itself is blocked.
    """
    result = evaluate(_payload("rm .git/MERGE_HEAD"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_tmp_not_blocked(rule):
    """rm -rf /tmp/test-dir falls through — not a .git path."""
    result = evaluate(_payload("rm -rf /tmp/test-dir"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_git_suffix_not_blocked(rule):
    """rm -rf config.git falls through — '.git' is a suffix, not the directory name.

    The pattern requires whitespace or '/' immediately before '.git', so
    filenames ending in .git (without a separator before it) don't match.
    """
    result = evaluate(_payload("rm -rf config.git"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_word_ending_in_rm_not_blocked(rule):
    """terraform fmt -recursive .git falls through — 'terraform' ends in 'rm' but is not rm."""
    result = evaluate(_payload("terraform fmt -recursive .git"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_rm_flag_not_blocked(rule):
    """docker run --rm ... grep -r TODO /src/.git falls through — --rm is a flag, not the rm command."""
    result = evaluate(_payload("docker run --rm -v .:/src alpine grep -r TODO /src/.git"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_later_command_not_blocked(rule):
    """rm -f out.log && grep -r TODO .git falls through — .git is an argument to grep, not rm."""
    result = evaluate(_payload("rm -f out.log && grep -r TODO .git"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_uppercase_r_flag(rule):
    """rm -Rf .git is denied — -R is rm's other recursive flag."""
    result = evaluate(_payload("rm -Rf .git"), [rule])
    assert result["decision"] == "deny"


def test_boundary_long_recursive_flag(rule):
    """rm --recursive --force .git is denied."""
    result = evaluate(_payload("rm --recursive --force .git"), [rule])
    assert result["decision"] == "deny"


def test_boundary_separator_after_target(rule):
    """rm -rf .git; git init is denied — a separator right after .git still ends the target."""
    result = evaluate(_payload("rm -rf .git; git init"), [rule])
    assert result["decision"] == "deny"


def test_boundary_quoted_path(rule):
    """rm -rf "$repo/.git" is denied — quoting the path doesn't hide it."""
    result = evaluate(_payload('rm -rf "$repo/.git"'), [rule])
    assert result["decision"] == "deny"


def test_boundary_rm_invoked_by_path(rule):
    """/bin/rm -rf .git is denied — calling rm by its full path is still rm."""
    result = evaluate(_payload("/bin/rm -rf .git"), [rule])
    assert result["decision"] == "deny"
