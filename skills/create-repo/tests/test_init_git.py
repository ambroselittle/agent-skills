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
    with patch(
        "scripts.init_git.subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")
    ):
        with pytest.raises(subprocess.CalledProcessError):
            run_cmd(["git", "bad-command"], Path("/tmp"))


# --- init_git ---


def test_init_git_local_only():
    """--no-github should skip GitHub and return None."""
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
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
        if "commit" in cmd:
            # Find the -m flag and capture the message
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


def test_init_git_with_github():
    """Should create a GitHub repo and return the URL."""

    def fake_run(cmd, **kwargs):
        check = kwargs.get("check", True)
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()  # Authenticated
        if "repo view" in cmd_str and "my-app" in cmd_str and "--json" in cmd_str:
            # Repo doesn't exist yet
            if not check:
                return _mock_run(returncode=1)
            raise subprocess.CalledProcessError(1, cmd)
        if "repo create" in cmd_str:
            return _mock_run(stdout="https://github.com/user/my-app\n")
        return _mock_run()

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
        return _mock_run()

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
    """Should raise if the GitHub repo already exists."""

    def fake_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "auth status" in cmd_str:
            return _mock_run()
        if "repo view" in cmd_str and "--json" in cmd_str:
            return _mock_run(stdout='{"url":"https://github.com/user/my-app"}')
        return _mock_run()

    with patch("scripts.init_git.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="already exists"):
            init_git(
                Path("/tmp/my-app"),
                "my-app",
                "fullstack-ts",
                "React + Hono",
                no_github=False,
            )
