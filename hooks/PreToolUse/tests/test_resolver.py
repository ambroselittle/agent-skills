"""Tests for path normalization and glob matching in resolver.py."""

import os
from pathlib import Path

from resolver import _glob_match, matches_path_pattern, normalize_path

HOME = str(Path.home())
REPO = "/repo/myproject"


# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


def test_normalize_expands_tilde():
    result = normalize_path("~/foo/bar")
    assert result == os.path.expanduser("~/foo/bar")
    assert not result.startswith("~")


def test_normalize_absolute_path_unchanged():
    # normalize_path does not follow symlinks, so /tmp stays /tmp even on macOS
    result = normalize_path("/tmp/foo")
    assert result == "/tmp/foo"


# ---------------------------------------------------------------------------
# _glob_match: basic patterns
# ---------------------------------------------------------------------------


def test_glob_exact_match():
    assert _glob_match("/a/b/c.py", "/a/b/c.py") is True


def test_glob_exact_no_match():
    assert _glob_match("/a/b/d.py", "/a/b/c.py") is False


def test_glob_star_matches_filename():
    assert _glob_match("/a/b/c.py", "/a/b/*.py") is True


def test_glob_star_does_not_cross_slash():
    assert _glob_match("/a/b/sub/c.py", "/a/b/*.py") is False


def test_glob_question_mark():
    assert _glob_match("/a/b/c.py", "/a/b/?.py") is True
    assert _glob_match("/a/b/cd.py", "/a/b/?.py") is False


# ---------------------------------------------------------------------------
# _glob_match: ** patterns
# ---------------------------------------------------------------------------


def test_double_star_matches_zero_components():
    # /base/**/.env should match /base/.env (zero intermediate dirs)
    assert _glob_match(f"{REPO}/.env", f"{REPO}/**/.env") is True


def test_double_star_matches_one_component():
    assert _glob_match(f"{REPO}/src/.env", f"{REPO}/**/.env") is True


def test_double_star_matches_multiple_components():
    assert _glob_match(f"{REPO}/src/deep/nested/.env", f"{REPO}/**/.env") is True


def test_double_star_no_match_wrong_base():
    assert _glob_match("/other/project/.env", f"{REPO}/**/.env") is False


def test_double_star_no_match_wrong_suffix():
    assert _glob_match(f"{REPO}/src/main.py", f"{REPO}/**/.env") is False


# ---------------------------------------------------------------------------
# matches_path_pattern: anchored ~ paths
# ---------------------------------------------------------------------------


def test_tilde_anchored_matches_home():
    ssh_key = f"{HOME}/.ssh/id_rsa"
    assert matches_path_pattern(ssh_key, "~/.ssh/*", None, REPO) is True


def test_tilde_anchored_no_match_different_dir():
    other = f"{HOME}/projects/.ssh/id_rsa"
    # ~/.ssh/* should not match ~/projects/.ssh/id_rsa
    assert matches_path_pattern(other, "~/.ssh/*", None, REPO) is False


def test_tilde_anchored_matches_specific_file():
    credentials = f"{HOME}/.aws/credentials"
    assert matches_path_pattern(credentials, "~/.aws/credentials", None, REPO) is True


# ---------------------------------------------------------------------------
# matches_path_pattern: anchored / paths
# ---------------------------------------------------------------------------


def test_absolute_anchored_matches():
    assert matches_path_pattern("/etc/passwd", "/etc/passwd", None, "") is True


def test_absolute_anchored_no_match():
    assert matches_path_pattern("/etc/hosts", "/etc/passwd", None, "") is False


# ---------------------------------------------------------------------------
# matches_path_pattern: unanchored patterns
# ---------------------------------------------------------------------------


def test_unanchored_uses_repo_root():
    # **/.env resolved against REPO
    path = f"{REPO}/src/.env"
    assert matches_path_pattern(path, "**/.env", REPO, "") is True


def test_unanchored_does_not_match_outside_repo():
    path = "/other/project/.env"
    assert matches_path_pattern(path, "**/.env", REPO, "") is False


def test_unanchored_falls_back_to_cwd_when_no_repo():
    cwd = "/home/user/work"
    path = f"{cwd}/.env"
    assert matches_path_pattern(path, "**/.env", None, cwd) is True


def test_unanchored_env_star_matches_env_local():
    path = f"{REPO}/.env.local"
    assert matches_path_pattern(path, "**/.env.*", REPO, "") is True


def test_unanchored_envrc_matches():
    path = f"{REPO}/src/.envrc"
    assert matches_path_pattern(path, "**/.envrc", REPO, "") is True


# ---------------------------------------------------------------------------
# normalize_path: cwd-aware resolution
# ---------------------------------------------------------------------------


def test_normalize_relative_with_cwd():
    """Relative path is resolved against cwd, not the process cwd."""
    result = normalize_path(".env", cwd="/repo/myproject")
    assert result == "/repo/myproject/.env"


def test_normalize_relative_no_cwd_uses_process_cwd():
    """Without cwd, falls back to os.path.abspath (process-relative)."""
    import os

    result = normalize_path("somefile.txt")
    assert result == os.path.abspath("somefile.txt")


def test_normalize_absolute_ignores_cwd():
    """Absolute path is returned as-is regardless of cwd."""
    result = normalize_path("/etc/passwd", cwd="/some/other/dir")
    assert result == "/etc/passwd"


def test_normalize_tilde_ignores_cwd():
    """Tilde paths expand to home and are treated as absolute."""
    result = normalize_path("~/.ssh/id_rsa", cwd="/some/other/dir")
    assert result == str(Path.home() / ".ssh/id_rsa")


# ---------------------------------------------------------------------------
# matches_path_pattern: relative path in payload resolved against cwd
# ---------------------------------------------------------------------------


def test_relative_path_resolved_against_cwd_matches():
    """'.env' in repo cwd correctly matches **/.env pattern."""
    assert matches_path_pattern(".env", "**/.env", REPO, REPO) is True


def test_relative_path_dotenv_local_resolved():
    """.env.local in repo cwd matches **/.env.* pattern."""
    assert matches_path_pattern(".env.local", "**/.env.*", REPO, REPO) is True


def test_relative_path_outside_repo_does_not_match():
    """Relative path that resolves outside repo root does not match."""
    # ../../secret.env resolves to /secret.env which is outside REPO
    assert matches_path_pattern("../../secret.env", "**/.env", REPO, REPO) is False
