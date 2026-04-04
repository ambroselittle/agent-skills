"""Tests for rule: Block rm targeting home directory."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block rm targeting home directory — rm ~/ would destroy the user environment"
RULE_ID = "block-rm-home"


def _payload(command, cwd=REPO):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_match(rule):
    """rm -rf ~/ is denied."""
    result = evaluate(_payload("rm -rf ~/"), [rule])
    assert result["decision"] == "deny"


def test_no_match(rule):
    """rm -rf build/ falls through — not a home path."""
    result = evaluate(_payload("rm -rf build/"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_home_subdirectory(rule):
    """rm -rf ~/Documents is denied — anything under home is protected."""
    result = evaluate(_payload("rm -rf ~/Documents"), [rule])
    assert result["decision"] == "deny"


def test_boundary_home_deep_path(rule):
    """rm -rf ~/projects/foo/bar is denied."""
    result = evaluate(_payload("rm -rf ~/projects/foo/bar"), [rule])
    assert result["decision"] == "deny"


def test_boundary_rm_file_in_home(rule):
    """rm ~/secrets is denied — even non-recursive rm on home paths is blocked."""
    result = evaluate(_payload("rm ~/secrets"), [rule])
    assert result["decision"] == "deny"


def test_boundary_chained_with_home(rule):
    """rm ~/file chained with another command is denied."""
    result = evaluate(_payload("ls && rm ~/file"), [rule])
    assert result["decision"] == "deny"


def test_boundary_tmp_not_blocked(rule):
    """rm -rf /tmp/cleanup falls through — /tmp is not ~/."""
    result = evaluate(_payload("rm -rf /tmp/cleanup"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_absolute_path_not_blocked(rule):
    """rm -rf /var/log/app falls through — not a home path."""
    result = evaluate(_payload("rm -rf /var/log/app"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_tilde_mid_path_not_blocked(rule):
    """rm /some/path/~/nope falls through — ~ with preceding / is not a home expansion.

    The pattern requires whitespace before ~/, so a bare tilde mid-path
    (without preceding whitespace) does not trigger the rule.
    """
    result = evaluate(_payload("rm -rf /some/path/~/nope"), [rule])
    assert result["decision"] == "proceed"


def test_boundary_rm_absolute_chained_with_tilde_in_later_command(rule):
    """rm /absolute/path && tail ~/.log falls through — ~/. is not an arg to rm.

    The rm targets an absolute path; ~/ appears only in a later subcommand.
    Greedy matching across && must not cause a false positive.
    """
    result = evaluate(_payload("rm /tmp/hook-test.tmp && tail -3 ~/.claude/audit.log"), [rule])
    assert result["decision"] == "proceed"
