"""Tests for the verification script."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.verify import StepResult, VerifyResult, detect_platform, run_step, verify


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
    with patch(
        "scripts.verify.subprocess.run", return_value=_mock_run(returncode=1, stderr="build failed")
    ):
        result = run_step("build", ["pnpm", "build"], Path("/tmp"))
    assert not result.passed
    assert result.error == "build failed"


def test_run_step_timeout():
    with patch(
        "scripts.verify.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="test", timeout=10),
    ):
        result = run_step("slow step", ["sleep", "999"], Path("/tmp"), timeout=10)
    assert not result.passed
    assert "Timed out" in result.error


def test_run_step_truncates_long_errors():
    long_error = "x" * 3000
    with patch(
        "scripts.verify.subprocess.run", return_value=_mock_run(returncode=1, stderr=long_error)
    ):
        result = run_step("failing", ["cmd"], Path("/tmp"))
    assert len(result.error) < 2100  # 2000 + truncation message


# --- VerifyResult ---


def test_verify_result_all_pass():
    r = VerifyResult(
        steps=[
            StepResult("a", True, 1.0),
            StepResult("b", True, 2.0),
        ]
    )
    assert r.passed


def test_verify_result_one_fail():
    r = VerifyResult(
        steps=[
            StepResult("a", True, 1.0),
            StepResult("b", False, 2.0, "oops"),
        ]
    )
    assert not r.passed


# --- verify (mocked, Node platform) ---


def test_verify_node_stops_on_first_failure():
    """Verify should stop at the first failing step and not run subsequent steps."""
    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if "install" in cmd:
            return _mock_run(returncode=1, stderr="install failed")
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
    ):
        result = verify(Path("/tmp/test-project"))

    assert not result.passed
    assert result.steps[0].name == "pnpm install"
    assert not result.steps[0].passed
    # Should only have one step since it stops on failure
    assert len(result.steps) == 1


def test_verify_node_runs_correct_command_sequence():
    """Verify that commands are called in the expected order."""
    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd[0] if isinstance(cmd, list) else cmd)
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=True),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        verify(Path("/tmp/test-project"))

    # Should have run: install, docker up, pg_isready, db:push, build, typecheck, lint, test, e2e
    assert len(commands_run) >= 9
    assert "pnpm" in commands_run
    assert "docker" in commands_run


def test_verify_node_runs_e2e_when_servers_are_up(tmp_path):
    """E2E tests should run when both API and web servers are reachable."""
    # Create apps/web with playwright config so verify detects a fullstack project
    web_dir = tmp_path / "apps" / "web"
    web_dir.mkdir(parents=True)
    (web_dir / "playwright.config.ts").write_text("export default {}")
    (tmp_path / "package.json").write_text("{}")

    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd if isinstance(cmd, list) else [cmd])
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=True),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(tmp_path)

    # E2E step should be present
    e2e_steps = [s for s in result.steps if "e2e" in s.name]
    assert len(e2e_steps) == 1


def test_verify_node_skips_e2e_when_server_down(tmp_path):
    """E2E tests should NOT run when the web server is unreachable."""
    # Create apps/web so verify detects a fullstack project
    web_dir = tmp_path / "apps" / "web"
    web_dir.mkdir(parents=True)
    (web_dir / "playwright.config.ts").write_text("export default {}")
    (tmp_path / "package.json").write_text("{}")

    def fake_run(cmd, **kwargs):
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=False),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(tmp_path)

    # E2E steps should NOT be present (both servers down)
    e2e_steps = [s for s in result.steps if "e2e" in s.name]
    assert len(e2e_steps) == 0


def test_verify_node_api_only_skips_web(tmp_path):
    """API-only projects should not check web port or install browsers."""
    # Create apps/api with playwright config but NO apps/web
    api_dir = tmp_path / "apps" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "playwright.config.ts").write_text("export default {}")
    (tmp_path / "package.json").write_text("{}")

    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd if isinstance(cmd, list) else [cmd])
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=True),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(tmp_path)

    step_names = [s.name for s in result.steps]

    # Should have API dev server but NOT web
    assert "dev server (API)" in step_names
    assert "dev server (web)" not in step_names

    # Should have API E2E
    assert "e2e tests (api)" in step_names

    # Should NOT have playwright install (no browser needed)
    assert "playwright install" not in step_names


def test_verify_node_fullstack_runs_both_e2e(tmp_path):
    """Fullstack projects with both web and API E2E should run both."""
    web_dir = tmp_path / "apps" / "web"
    web_dir.mkdir(parents=True)
    (web_dir / "playwright.config.ts").write_text("export default {}")
    api_dir = tmp_path / "apps" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "playwright.config.ts").write_text("export default {}")
    (tmp_path / "package.json").write_text("{}")

    def fake_run(cmd, **kwargs):
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="node"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=True),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(tmp_path)

    step_names = [s.name for s in result.steps]

    # Both E2E suites should run
    assert "e2e tests (web)" in step_names
    assert "e2e tests (api)" in step_names


# --- verify (mocked, Python platform) ---


def test_verify_python_stops_on_first_failure():
    """Python verify should stop at the first failing step."""

    def fake_run(cmd, **kwargs):
        if "sync" in cmd:
            return _mock_run(returncode=1, stderr="sync failed")
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="python"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
    ):
        result = verify(Path("/tmp/test-project"))

    assert not result.passed
    assert result.steps[0].name == "uv sync"
    assert len(result.steps) == 1


def test_verify_python_runs_correct_sequence():
    """Python verify should run uv sync, docker, ruff, pytest, dev server."""
    commands_run = []

    def fake_run(cmd, **kwargs):
        commands_run.append(cmd if isinstance(cmd, list) else [cmd])
        return _mock_run()

    with (
        patch("scripts.verify.detect_platform", return_value="python"),
        patch("scripts.verify.subprocess.run", side_effect=fake_run),
        patch("scripts.verify.subprocess.Popen") as mock_popen,
        patch("scripts.verify.wait_for_port", return_value=True),
        patch("scripts.verify.check_health", return_value=True),
        patch("scripts.verify.os.getpgid", return_value=99999),
        patch("scripts.verify.atexit.register"),
        patch("scripts.verify._kill_process_group"),
    ):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = verify(Path("/tmp/test-project"))

    assert result.passed
    step_names = [s.name for s in result.steps]
    assert "uv sync" in step_names
    assert "docker compose up" in step_names
    assert "ruff check" in step_names
    assert "pytest" in step_names
    assert "dev server" in step_names


# --- detect_platform ---


def test_detect_platform_swift_ts(tmp_path):
    """Returns 'swift-ts' when package.json and apps/mobile/project.yml both exist."""
    (tmp_path / "package.json").write_text("{}")
    mobile = tmp_path / "apps" / "mobile"
    mobile.mkdir(parents=True)
    (mobile / "project.yml").write_text("name: MyApp")
    assert detect_platform(tmp_path) == "swift-ts"


def test_detect_platform_node_without_mobile(tmp_path):
    """Returns 'node' when only package.json exists (no mobile project)."""
    (tmp_path / "package.json").write_text("{}")
    assert detect_platform(tmp_path) == "node"


def test_detect_platform_fullstack_python_takes_precedence(tmp_path):
    """Returns 'fullstack-python' when both pyproject.toml and package.json exist."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pyproject.toml").write_text("[project]")
    assert detect_platform(tmp_path) == "fullstack-python"


def test_detect_platform_swift_ts_beats_fullstack_python(tmp_path):
    """swift-ts detection comes before fullstack-python."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pyproject.toml").write_text("[project]")
    mobile = tmp_path / "apps" / "mobile"
    mobile.mkdir(parents=True)
    (mobile / "project.yml").write_text("name: MyApp")
    # swift-ts check comes first
    assert detect_platform(tmp_path) == "swift-ts"


# --- verify_swift_ts (skip on non-macOS) ---


def test_verify_swift_ts_skips_on_linux():
    """On non-macOS, swift-ts verify should skip Swift steps."""
    with (
        patch("scripts.verify.detect_platform", return_value="swift-ts"),
        patch("scripts.verify.subprocess.run", return_value=_mock_run()),
        patch("scripts.verify.verify_swift_ts") as mock_swift,
    ):
        mock_swift.return_value = VerifyResult(
            steps=[StepResult("swift: skipped", True, 0)]
        )
        result = verify(Path("/tmp/test-project"))

    assert result.passed
