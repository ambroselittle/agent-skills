"""Unit tests for filesystem operation handlers."""
from pathlib import Path

import pytest

from operations.filesystem import matches_read_path, matches_write_path, matches_delete_path

HOME = str(Path.home())
REPO = "/repo/myproject"

SSH_RULE = {
    "paths": [f"{HOME}/.ssh/*"],
    "action": "deny",
}

ENV_RULE = {
    "paths": ["**/.env", "**/.env.*", "**/.envrc"],
    "action": "deny",
}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": REPO}


def read_tool(path):
    return {"tool_name": "Read", "tool_input": {"file_path": path}, "cwd": REPO}


def edit_tool(path):
    return {"tool_name": "Edit", "tool_input": {"file_path": path}, "cwd": REPO}


def write_tool(path):
    return {"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": REPO}


# ---------------------------------------------------------------------------
# matches_read_path
# ---------------------------------------------------------------------------

class TestMatchesReadPath:
    def test_read_tool_matches_ssh_key(self):
        p = read_tool(f"{HOME}/.ssh/id_rsa")
        assert matches_read_path(p, SSH_RULE, None, REPO) is True

    def test_read_tool_no_match_normal_file(self):
        p = read_tool(f"{REPO}/main.py")
        assert matches_read_path(p, SSH_RULE, None, REPO) is False

    def test_bash_cat_matches_ssh_key(self):
        p = bash(f"cat {HOME}/.ssh/id_rsa")
        assert matches_read_path(p, SSH_RULE, None, REPO) is True

    def test_bash_head_matches_ssh_key(self):
        p = bash(f"head {HOME}/.ssh/known_hosts")
        assert matches_read_path(p, SSH_RULE, None, REPO) is True

    def test_bash_grep_matches_ssh_key(self):
        p = bash(f"grep something {HOME}/.ssh/config")
        assert matches_read_path(p, SSH_RULE, None, REPO) is True

    def test_bash_tail_no_match_other_file(self):
        p = bash(f"tail /var/log/syslog")
        assert matches_read_path(p, SSH_RULE, None, REPO) is False

    def test_bash_cat_env_file_unanchored(self):
        p = bash(f"cat {REPO}/.env")
        assert matches_read_path(p, ENV_RULE, REPO, REPO) is True

    def test_bash_cat_env_nested(self):
        p = bash(f"cat {REPO}/src/.env.local")
        assert matches_read_path(p, ENV_RULE, REPO, REPO) is True

    def test_python_open_matches(self):
        p = bash(f"python3 -c \"open('{HOME}/.ssh/id_rsa')\"")
        assert matches_read_path(p, SSH_RULE, None, REPO) is True

    def test_edit_tool_does_not_match_read(self):
        # Edit is a write operation, not a read
        p = edit_tool(f"{HOME}/.ssh/id_rsa")
        assert matches_read_path(p, SSH_RULE, None, REPO) is False

    def test_non_read_command_no_match(self):
        p = bash("git status")
        assert matches_read_path(p, SSH_RULE, None, REPO) is False


# ---------------------------------------------------------------------------
# matches_write_path
# ---------------------------------------------------------------------------

class TestMatchesWritePath:
    WRITE_RULE = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}

    def test_write_tool_matches(self):
        p = write_tool(f"{HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_edit_tool_matches(self):
        p = edit_tool(f"{HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_bash_cp_matches_destination(self):
        p = bash(f"cp /tmp/key {HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_bash_redirect_write(self):
        p = bash(f"echo 'key' > {HOME}/.ssh/new_key")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_bash_mv_matches(self):
        p = bash(f"mv /tmp/new.key {HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_no_match_normal_write(self):
        p = write_tool(f"{REPO}/main.py")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is False

    def test_read_tool_does_not_match_write(self):
        p = read_tool(f"{HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is False


# ---------------------------------------------------------------------------
# matches_delete_path
# ---------------------------------------------------------------------------

class TestMatchesDeletePath:
    DELETE_RULE = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}

    def test_rm_matches(self):
        p = bash(f"rm {HOME}/.ssh/id_rsa")
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is True

    def test_rm_rf_matches(self):
        # ~/.ssh/* matches files inside the dir; use a file path, not the dir itself
        p = bash(f"rm -rf {HOME}/.ssh/id_rsa")
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is True

    def test_rmdir_matches(self):
        p = bash(f"rmdir {HOME}/.ssh")
        # ~/.ssh/* won't match ~/.ssh (the dir itself) unless pattern allows it
        # Use a broader rule for this test
        rule = {"paths": [f"{HOME}/.ssh*"], "action": "deny"}
        assert matches_delete_path(p, rule, None, REPO) is True

    def test_no_match_other_path(self):
        p = bash("rm /tmp/tempfile")
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is False

    def test_non_bash_returns_false(self):
        p = {"tool_name": "Read", "tool_input": {"file_path": f"{HOME}/.ssh/id_rsa"}, "cwd": REPO}
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is False

    def test_non_delete_command_no_match(self):
        p = bash(f"cat {HOME}/.ssh/id_rsa")
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is False


# ---------------------------------------------------------------------------
# Compound command splitting
# ---------------------------------------------------------------------------

class TestCompoundCommands:
    """Verify that sensitive operations in compound commands are caught."""

    SSH_RULE = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}
    WRITE_RULE = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}
    DELETE_RULE = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}

    def test_read_after_and_and(self):
        p = bash(f"echo ok && cat {HOME}/.ssh/id_rsa")
        assert matches_read_path(p, self.SSH_RULE, None, REPO) is True

    def test_read_after_semicolon(self):
        p = bash(f"cd /tmp; cat {HOME}/.ssh/id_rsa")
        assert matches_read_path(p, self.SSH_RULE, None, REPO) is True

    def test_read_after_pipe(self):
        p = bash(f"echo x | cat {HOME}/.ssh/id_rsa")
        assert matches_read_path(p, self.SSH_RULE, None, REPO) is True

    def test_read_before_and_and(self):
        p = bash(f"cat {HOME}/.ssh/id_rsa && echo done")
        assert matches_read_path(p, self.SSH_RULE, None, REPO) is True

    def test_write_after_and_and(self):
        p = bash(f"echo ok && cp /tmp/key {HOME}/.ssh/id_rsa")
        assert matches_write_path(p, self.WRITE_RULE, None, REPO) is True

    def test_delete_after_and_and(self):
        p = bash(f"echo ok && rm {HOME}/.ssh/id_rsa")
        assert matches_delete_path(p, self.DELETE_RULE, None, REPO) is True

    def test_safe_compound_no_match(self):
        p = bash("git status && echo done")
        assert matches_read_path(p, self.SSH_RULE, None, REPO) is False
