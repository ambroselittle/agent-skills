"""Unit tests for filesystem operation handlers."""

from pathlib import Path

from operations.filesystem import matches_delete_path, matches_read_path, matches_write_path

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
        p = bash("tail /var/log/syslog")
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


# ---------------------------------------------------------------------------
# Case sensitivity: insensitive by default, "case-sensitive": true opts out
# ---------------------------------------------------------------------------


class TestCaseSensitivity:
    SECRET_RULE = {
        "paths": ["/**/*secret*"],
        "action": "deny",
    }

    SECRET_RULE_SENSITIVE = {
        "paths": ["/**/*secret*"],
        "case-sensitive": True,
        "action": "deny",
    }

    def test_read_matches_other_casing_by_default(self):
        p = read_tool(f"{REPO}/ClientSECRET.json")
        assert matches_read_path(p, self.SECRET_RULE, REPO, REPO) is True

    def test_bash_read_matches_other_casing_by_default(self):
        p = bash(f"cat {REPO}/PROD_Secrets.txt")
        assert matches_read_path(p, self.SECRET_RULE, REPO, REPO) is True

    def test_case_sensitive_rule_requires_exact_case(self):
        p = read_tool(f"{REPO}/ClientSECRET.json")
        assert matches_read_path(p, self.SECRET_RULE_SENSITIVE, REPO, REPO) is False

    def test_case_sensitive_rule_still_matches_exact_case(self):
        p = read_tool(f"{REPO}/client-secret.json")
        assert matches_read_path(p, self.SECRET_RULE_SENSITIVE, REPO, REPO) is True

    def test_write_matches_other_casing_by_default(self):
        rule = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}
        p = write_tool(f"{HOME}/.SSH/id_rsa")
        assert matches_write_path(p, rule, None, REPO) is True

    def test_delete_matches_other_casing_by_default(self):
        rule = {"paths": [f"{HOME}/.ssh/*"], "action": "deny"}
        p = bash(f"rm {HOME}/.SSH/id_rsa")
        assert matches_delete_path(p, rule, None, REPO) is True


# ---------------------------------------------------------------------------
# Path extraction: only real path arguments count, not content that merely
# resembles one (heredoc bodies, grep/sed/awk patterns, quoted text).
# ---------------------------------------------------------------------------

SECRET_RULE = {"paths": ["/**/*secret*"], "action": "deny"}


class TestHeredocBodiesIgnored:
    def test_heredoc_body_url_is_not_a_read(self):
        cmd = 'cat > payload.json <<\'EOF\'\n{"url": "https://api.example.com/oauth/secret"}\nEOF'
        assert matches_read_path(bash(cmd), SECRET_RULE, REPO, REPO) is False

    def test_heredoc_body_dotted_word_is_not_a_read(self):
        cmd = "cat > notes.md <<'EOF'\nSee secrets.json for details.\nEOF"
        assert matches_read_path(bash(cmd), SECRET_RULE, REPO, REPO) is False

    def test_heredoc_body_redirect_is_not_a_write(self):
        cmd = "cat > notes.md <<'EOF'\nrun: foo > /tmp/secret.txt\nEOF"
        assert matches_write_path(bash(cmd), SECRET_RULE, REPO, REPO) is False

    def test_heredoc_body_rm_is_not_a_delete(self):
        cmd = "cat > notes.md <<'EOF'\nrm /tmp/secret.txt\nEOF"
        assert matches_delete_path(bash(cmd), SECRET_RULE, REPO, REPO) is False

    def test_heredoc_redirect_target_still_a_write(self):
        cmd = "cat > /tmp/secret.txt <<'EOF'\nhello\nEOF"
        assert matches_write_path(bash(cmd), SECRET_RULE, REPO, REPO) is True

    def test_python_open_inside_heredoc_still_a_read(self):
        cmd = "python3 - <<'EOF'\nprint(open('/tmp/secrets.json').read())\nEOF"
        assert matches_read_path(bash(cmd), SECRET_RULE, REPO, REPO) is True


class TestPatternArgumentsIgnored:
    def test_sed_script_is_not_a_path(self):
        p = bash("sed -i 's/foo/secret/' config.txt")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_bsd_sed_inplace_empty_suffix(self):
        p = bash("sed -i '' 's/foo/secret/' config.txt")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_grep_pattern_is_not_a_path(self):
        p = bash('grep -rn "secret.key" src/')
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_awk_program_is_not_a_path(self):
        p = bash("awk '/secret.json/ {print}' app.log")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_grep_file_after_pattern_still_matches(self):
        p = bash(f"grep -i token {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_grep_explicit_pattern_flag_first_positional_is_file(self):
        p = bash(f"grep -e token {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_grep_double_dash_then_pattern_then_file(self):
        p = bash(f"grep -- -token {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_sed_file_after_script_still_matches(self):
        p = bash(f"sed -n p {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_awk_file_after_program_still_matches(self):
        p = bash(f"awk '{{print}}' {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_tail_follow_flag_does_not_swallow_file(self):
        p = bash(f"tail -f {REPO}/secrets.log")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True


class TestRedirectsAreTokenBased:
    def test_quoted_angle_bracket_is_not_a_read(self):
        p = bash('echo "<secret>abc</secret>" | curl -d @- https://example.com')
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_quoted_angle_bracket_is_not_a_write(self):
        p = bash('echo "a > /tmp/secret.txt" | tee out.log')
        assert matches_write_path(p, SECRET_RULE, REPO, REPO) is False

    def test_stdin_redirect_still_a_read(self):
        p = bash(f"wc -l < {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_stdin_redirect_no_space_still_a_read(self):
        p = bash(f"wc -l <{REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_stdin_redirect_on_non_read_command_still_a_read(self):
        p = bash(f"python3 script.py < {REPO}/secrets.env")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_here_string_is_not_a_read(self):
        p = bash("cat <<< secret.txt")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_append_redirect_still_a_write(self):
        p = bash(f"echo x >> {REPO}/secrets.env")
        assert matches_write_path(p, SECRET_RULE, REPO, REPO) is True

    def test_redirect_no_space_still_a_write(self):
        p = bash(f"echo x >{REPO}/secrets.env")
        assert matches_write_path(p, SECRET_RULE, REPO, REPO) is True

    def test_stderr_merge_is_not_a_write_target(self):
        p = bash("make build 2>&1")
        assert matches_write_path(p, SECRET_RULE, REPO, REPO) is False


class TestBarePathsRequireExistence:
    """A bare token (no slash, no glob) only counts as a read target if it exists on disk."""

    def test_missing_bare_dotted_token_is_not_a_path(self):
        p = bash("cat secret.txt")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is False

    def test_existing_bare_token_is_a_path(self, tmp_path):
        (tmp_path / "secrets.json").write_text("{}")
        p = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat secrets.json"},
            "cwd": str(tmp_path),
        }
        assert matches_read_path(p, SECRET_RULE, str(tmp_path), str(tmp_path)) is True

    def test_existing_bare_token_without_extension_is_a_path(self, tmp_path):
        (tmp_path / "secrets").write_text("{}")
        p = {"tool_name": "Bash", "tool_input": {"command": "cat secrets"}, "cwd": str(tmp_path)}
        assert matches_read_path(p, SECRET_RULE, str(tmp_path), str(tmp_path)) is True

    def test_cd_then_bare_token_resolves_against_new_dir(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "secrets.json").write_text("{}")
        p = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd sub && cat secrets.json"},
            "cwd": str(tmp_path),
        }
        assert matches_read_path(p, SECRET_RULE, str(tmp_path), str(tmp_path)) is True

    def test_unresolvable_cd_falls_back_to_name_heuristic(self):
        p = bash('cd "$(git rev-parse --show-toplevel)" && cat secrets.json')
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_glob_token_is_a_path(self):
        p = bash("cat *secret*")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_relative_path_with_slash_is_a_path(self):
        p = bash("cat config/secrets.yaml")
        assert matches_read_path(p, SECRET_RULE, REPO, REPO) is True

    def test_write_bare_dotted_token_still_a_path(self):
        # Writes can create files, so a missing bare name still counts.
        p = bash("cp notes.txt secrets.json")
        assert matches_write_path(p, SECRET_RULE, REPO, REPO) is True

    def test_delete_bare_dotted_token_still_a_path(self):
        p = bash("rm secrets.json")
        assert matches_delete_path(p, SECRET_RULE, REPO, REPO) is True
