"""Tests for the git initialization script."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.init_git import init_git, run_cmd


def _mock_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# --- run_cmd ---


def test_run_cmd_success():
    with patch("scripts.init_git.subprocess.run", return_value=_mock_run()) as mock:
        result = run_cmd(["git", "status"], Path("/tmp"))
    assert result.returncode == 0
    mock.assert_called_once()


def test_run_cmd_failure_raises():
    with patch("scripts.init_git.subprocess.run", return_value=_mock_run(returncode=1, stderr="bad")):
        with pytest.raises(subprocess.CalledProcessError):
            run_cmd(["git", "bad-command"], Path("/tmp"))


# --- init_git ---


def test_init_git_local_only():
    """--no-github should skip GitHub and return None."""
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        cmd_str = " ".join(cmd)
        if "rev-parse" in cmd_str:
            return _mock_run(returncode=1)  # No commits yet — fresh repo
        if "status" in cmd_str and "--porcelain" in cmd_str:
            return _mock_run(stdout="A  file.txt")  # Staged changes to commit
        return _mock_run()

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        url = init_git(
            Path("/tmp/my-app"),
            "my-app",
            "fullstack-ts",
            "React + Hono + tRPC",
            no_github=True,
        )

    assert url is None
    # Should have: git init, git add -A, git commit
    cmd_strs = [" ".join(c) for c in commands]
    assert any("git init" in c for c in cmd_strs)
    assert any("git add -A" in c for c in cmd_strs)
    assert any("git commit" in c for c in cmd_strs)
    # Should NOT have gh commands
    assert not any("gh" in c for c in cmd_strs)


def test_init_git_commit_message_format():
    """Commit message should include template name and stack description."""
    commit_msg = None

    def fake_run(cmd, **kwargs):
        nonlocal commit_msg
        cmd_str = " ".join(cmd)
        if "rev-parse" in cmd_str:
            return _mock_run(returncode=1)  # No commits yet
        if "status" in cmd_str and "--porcelain" in cmd_str:
            return _mock_run(stdout="A  file.txt")  # Has changes to commit
        if "commit" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "-m" and i + 1 < len(cmd):
                    commit_msg = cmd[i + 1]
        return _mock_run()

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        init_git(
            Path("/tmp/my-app"),
            "my-app",
            "fullstack-ts",
            "React 19 + Hono + tRPC + Prisma",
            no_github=True,
        )

    assert commit_msg is not None
    assert "fullstack-ts" in commit_msg
    assert "React 19 + Hono + tRPC + Prisma" in commit_msg


def _fresh_repo_run(cmd, **kwargs):
    """Default fake_run for a fresh repo with no prior commits."""
    cmd_str = " ".join(cmd)
    if "rev-parse" in cmd_str:
        return _mock_run(returncode=1)  # No commits yet
    if "status" in cmd_str and "--porcelain" in cmd_str:
        return _mock_run(stdout="A  file.txt")  # Has changes to commit
    return _mock_run()


def test_init_git_with_github():
    """Should create a GitHub repo and return the URL."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "my-app" in cmd_str and "--json" in cmd_str:
            return _mock_run(returncode=1)  # Repo doesn't exist yet
        if "repo create" in cmd_str:
            return _mock_run(stdout="https://github.com/user/my-app\n")
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        url = init_git(
            Path("/tmp/my-app"),
            "my-app",
            "fullstack-ts",
            "React + Hono",
            no_github=False,
        )

    assert url == "https://github.com/user/my-app"


def test_init_git_not_authenticated():
    """Should raise if gh is not authenticated."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run(returncode=1, stderr="not logged in")
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="not authenticated"):
            init_git(
                Path("/tmp/my-app"),
                "my-app",
                "fullstack-ts",
                "React + Hono",
                no_github=False,
            )


def test_init_git_repo_already_exists():
    """Should raise if the GitHub repo already exists and is non-empty."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "--json" in cmd_str:
            return _mock_run(stdout='{"url":"https://github.com/user/my-app","isEmpty":false}')
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="already exists"):
            init_git(
                Path("/tmp/my-app"),
                "my-app",
                "fullstack-ts",
                "React + Hono",
                no_github=False,
            )


def test_init_git_retries_on_transient_failure():
    """A transient push failure should be retried and succeed on the next attempt."""
    attempt_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal attempt_count
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "--json" in cmd_str:
            return _mock_run(returncode=1)  # Repo doesn't exist
        if "repo create" in cmd_str:
            attempt_count += 1
            if attempt_count == 1:
                return _mock_run(returncode=1, stderr="transient network error")
            return _mock_run(stdout="https://github.com/user/my-app\n")
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with patch("scripts.init_git.time.sleep"):
            url = init_git(
                Path("/tmp/my-app"),
                "my-app",
                "fullstack-ts",
                "React + Hono",
                no_github=False,
            )

    assert url == "https://github.com/user/my-app"
    assert attempt_count == 2


def test_init_git_retries_partial_state():
    """If repo was created but push failed, retry should detect the empty repo and push."""
    attempt_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal attempt_count
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "--json" in cmd_str:
            # First attempt: repo doesn't exist. Second attempt: repo exists but empty.
            if attempt_count == 0:
                return _mock_run(returncode=1)
            return _mock_run(stdout='{"url":"https://github.com/user/my-app","isEmpty":true}')
        if "repo create" in cmd_str:
            attempt_count += 1
            return _mock_run(returncode=1, stderr="push failed mid-way")
        if "git push" in cmd_str:
            return _mock_run()
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with patch("scripts.init_git.time.sleep"):
            url = init_git(
                Path("/tmp/my-app"),
                "my-app",
                "fullstack-ts",
                "React + Hono",
                no_github=False,
            )

    assert url == "https://github.com/user/my-app"


def test_init_git_exhausts_retries():
    """Should raise after all retry attempts are exhausted."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "--json" in cmd_str:
            return _mock_run(returncode=1)  # Repo never exists
        if "repo create" in cmd_str:
            return _mock_run(returncode=1, stderr="persistent error")
        return _fresh_repo_run(cmd, **kwargs)

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with patch("scripts.init_git.time.sleep"):
            with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
                init_git(
                    Path("/tmp/my-app"),
                    "my-app",
                    "fullstack-ts",
                    "React + Hono",
                    no_github=False,
                )
