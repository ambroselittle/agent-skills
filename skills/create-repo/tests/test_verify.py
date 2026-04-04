"""Tests for the verification script."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from scripts.verify import StepResult, VerifyResult, run_step, verify


def _mock_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# --- run_step ---


def test_run_step_success():
    with patch("scripts.verify.subprocess.run", return_value=_mock_run()):
        result = run_step("test step", ["echo", "hello"], Path("/tmp"))
    assert result.passed
    assert result.name == "test step"
    assert result.error is None


def test_run_step_failure():
    with patch("scripts.verify.subprocess.run", return_value=_mock_run(returncode=1, stderr="build failed")):
        result = run_step("build", ["pnpm", "build"], Path("/tmp"))
    assert not result.passed
    assert result.error == "build failed"


def test_run_step_timeout():
    with patch("scripts.verify.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=10)):
        result = run_step("slow step", ["sleep", "999"], Path("/tmp"), timeout=10)
    assert not result.passed
    assert "Timed out" in result.error


def test_run_step_truncates_long_errors():
    long_error = "x" * 3000
    with patch("scripts.verify.subprocess.run", return_value=_mock_run(returncode=1, stderr=long_error)):
        result = run_step("failing", ["cmd"], Path("/tmp"))
    assert len(result.error) < 2100  # 2000 + truncation message


# --- VerifyResult ---


def test_verify_result_all_pass():
    r = VerifyResult(steps=[
        StepResult("a", True, 1.0),
        StepResult("b", True, 2.0),
    ])
    assert r.passed


def test_verify_result_one_fail():
    r = VerifyResult(steps=[
        StepResult("a", True, 1.0),
        StepResult("b", False, 2.0, "oops"),
    ])
    assert not r.passed


# --- verify (mocked) ---


def test_verify_stops_on_first_failure():
    """Verify should stop at the first failing step and not run subsequent steps."""
    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if "install" in cmd:
            return _mock_run(returncode=1, stderr="install failed")
        return _mock_run()

    with patch("scripts.verify.subprocess.run", side_effect=fake_run):
        result = verify(Path("/tmp/test-project"))

    assert not result.passed
    assert result.steps[0].name == "pnpm install"
    assert not result.steps[0].passed
    # Should only have one step since it stops on failure
    assert len(result.steps) == 1


def test_verify_runs_correct_command_sequence():
    """Verify that commands are called in the expected order."""
    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd[0] if isinstance(cmd, list) else cmd)
        return _mock_run()

    with patch("scripts.verify.subprocess.run", side_effect=fake_run), \
         patch("scripts.verify.subprocess.Popen") as mock_popen, \
         patch("scripts.verify.wait_for_port", return_value=True), \
         patch("scripts.verify.check_health", return_value=True):

        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(Path("/tmp/test-project"))

    # Should have run: install, docker up, pg_isready, db:push, build, typecheck, lint, test, e2e
    assert len(commands_run) >= 9
    assert "pnpm" in commands_run
    assert "docker" in commands_run


def test_verify_runs_e2e_when_servers_are_up():
    """E2E tests should run when both API and web servers are reachable."""
    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd if isinstance(cmd, list) else [cmd])
        return _mock_run()

    with patch("scripts.verify.subprocess.run", side_effect=fake_run), \
         patch("scripts.verify.subprocess.Popen") as mock_popen, \
         patch("scripts.verify.wait_for_port", return_value=True), \
         patch("scripts.verify.check_health", return_value=True):

        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(Path("/tmp/test-project"))

    # E2E step should be present (runs via its own subprocess.run, not through run_step mock)
    e2e_steps = [s for s in result.steps if s.name == "e2e tests"]
    assert len(e2e_steps) == 1


def test_verify_skips_e2e_when_server_down():
    """E2E tests should NOT run when the web server is unreachable."""
    def fake_run(cmd, **kwargs):
        return _mock_run()

    with patch("scripts.verify.subprocess.run", side_effect=fake_run), \
         patch("scripts.verify.subprocess.Popen") as mock_popen, \
         patch("scripts.verify.wait_for_port", return_value=False), \
         patch("scripts.verify.check_health", return_value=True):

        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(Path("/tmp/test-project"))

    # E2E step should NOT be present
    e2e_steps = [s for s in result.steps if s.name == "e2e tests"]
    assert len(e2e_steps) == 0
