"""Verify a scaffolded project builds, typechecks, lints, and tests.

Runs quality checks only — assumes the project is already set up (deps
installed, docker running, db pushed/migrated). Use ``setup_project()``
from ``scaffold.py`` for the setup phase.

Detects the project platform (Node/Python/fullstack-python) and runs
the appropriate tool chain.
"""

from __future__ import annotations

import argparse
import atexit
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import urlopen


@dataclass
class StepResult:
    name: str
    passed: bool
    duration_s: float
    error: str | None = None


@dataclass
class VerifyResult:
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.steps)


def run_step(
    name: str,
    cmd: list[str],
    cwd: Path,
    timeout: int = 300,
    env: dict | None = None,
    fail_on_output: list[str] | None = None,
) -> StepResult:
    """Run a single verification step and return the result.

    Args:
        fail_on_output: Optional list of regex patterns. If any match the combined
            stdout+stderr output (even when exit code is 0), the step fails. Use
            this to catch tools that report issues in output without a non-zero exit
            (e.g. biome info-level diagnostics).
    """
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = time.monotonic() - start
        combined = "\n".join(s for s in (proc.stderr.strip(), proc.stdout.strip()) if s)
        if proc.returncode != 0:
            # Combine stderr and stdout — tools like turbo put their own
            # error wrapper on stderr while the actual child error is on stdout.
            error = combined if combined else f"Exit code {proc.returncode}"
            # Truncate long error output
            if len(error) > 2000:
                error = error[:2000] + "\n... (truncated)"
            return StepResult(name=name, passed=False, duration_s=elapsed, error=error)
        if fail_on_output:
            for pattern in fail_on_output:
                m = re.search(pattern, combined)
                if m:
                    snippet = combined[:2000] + ("\n... (truncated)" if len(combined) > 2000 else "")
                    return StepResult(
                        name=name,
                        passed=False,
                        duration_s=elapsed,
                        error=f"Output matched failure pattern {pattern!r}:\n{snippet}",
                    )
        return StepResult(name=name, passed=True, duration_s=elapsed)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return StepResult(
            name=name, passed=False, duration_s=elapsed, error=f"Timed out after {timeout}s"
        )
    except FileNotFoundError:
        elapsed = time.monotonic() - start
        return StepResult(
            name=name, passed=False, duration_s=elapsed, error=f"Command not found: {cmd[0]}"
        )


def wait_for_port(port: int, host: str = "localhost", timeout: float = 30) -> bool:
    """Wait for a TCP port to become available."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def check_health(url: str, timeout: float = 10) -> bool:
    """Check if a URL returns a 200 response."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _kill_process_group(pgid: int) -> None:
    """Kill an entire process group, ignoring errors if already dead."""
    import signal

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            os.waitpid(-pgid, os.WNOHANG)
        except ChildProcessError:
            return
        time.sleep(0.5)


# Error patterns that indicate a dirty SIGINT exit.
# These are turbo/npm-specific error strings that appear when a child process
# errors out rather than shutting down cleanly. "Interrupted by SIGINT" is
# intentionally excluded — just and other process runners print it on a normal
# SIGINT-triggered shutdown, which is the expected exit path.
_DIRTY_EXIT_PATTERNS = [
    "ELIFECYCLE",
    "run failed",
    "Command failed",
]


def _sigint_and_check(
    proc: subprocess.Popen,
    pgid: int,
    stderr_file: str | None = None,
) -> StepResult:
    """Send SIGINT to a process group and verify clean exit.

    Returns a StepResult indicating whether the process exited cleanly
    (no error patterns in stderr, exit code 0 or SIGINT-related).
    """
    import signal

    start = time.monotonic()

    try:
        os.killpg(pgid, signal.SIGINT)
    except (ProcessLookupError, PermissionError):
        return StepResult("clean exit", True, 0)

    # Wait up to 10s for graceful shutdown
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # Force kill if it didn't exit
        _kill_process_group(pgid)
        elapsed = time.monotonic() - start
        return StepResult(
            "clean exit", False, elapsed, "Process did not exit within 10s after SIGINT"
        )

    elapsed = time.monotonic() - start

    # Read stderr if captured to a file
    errors: list[str] = []
    if stderr_file:
        try:
            stderr_content = Path(stderr_file).read_text()
            for pattern in _DIRTY_EXIT_PATTERNS:
                if pattern in stderr_content:
                    errors.append(pattern)
        except OSError:
            pass

    if errors:
        return StepResult(
            "clean exit",
            False,
            elapsed,
            f"Dirty exit — found error output: {', '.join(errors)}",
        )

    return StepResult("clean exit", True, elapsed)


def detect_platform(project_dir: Path) -> str:
    """Detect the project platform from its files.

    Returns 'swift-ts' if package.json and apps/ios/ directory both exist,
    'fullstack-python' if both pyproject.toml and package.json exist,
    'python' if only pyproject.toml, 'node' if only package.json.
    Raises ValueError if neither is found.
    """
    has_pyproject = (project_dir / "pyproject.toml").exists()
    has_package_json = (project_dir / "package.json").exists()
    has_mobile_dir = (project_dir / "apps" / "ios").is_dir()
    if has_package_json and has_mobile_dir:
        return "swift-ts"
    if has_pyproject and has_package_json:
        return "fullstack-python"
    if has_pyproject:
        return "python"
    if has_package_json:
        return "node"
    raise ValueError(f"Cannot detect platform in {project_dir}: no pyproject.toml or package.json")


# ---------------------------------------------------------------------------
# Docker / Postgres helpers (shared across platforms)
# ---------------------------------------------------------------------------


def _read_dotenv(dotenv_file: Path) -> dict[str, str]:
    """Parse a .env file and return key-value pairs (ignores comments and blanks)."""
    if not dotenv_file.exists():
        return {}
    result: dict[str, str] = {}
    for line in dotenv_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _teardown_docker(project_dir: Path) -> None:
    """Tear down docker compose stack."""
    if not project_dir.exists():
        return
    try:
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=project_dir,
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Node verification
# ---------------------------------------------------------------------------


def verify_node(
    project_dir: Path,
    api_port: int = 3001,
    web_port: int = 3000,
) -> VerifyResult:
    """Verify a Node/TypeScript scaffolded project.

    Assumes setup is already done (deps installed, docker running, db pushed).
    Reads ports from .env.ports if available.
    """
    result = VerifyResult()

    # Force a project-local turbo cache to prevent cross-worktree cache
    # pollution (turbo matches on content hash, not path, so eval runs in
    # different worktrees share stale cached logs with wrong absolute paths).
    turbo_env = {**os.environ, "TURBO_CACHE_DIR": str(project_dir / ".turbo")}

    # Read discovered ports from .env.ports (written by setup)
    ports_file = project_dir / ".env.ports"
    if ports_file.exists():
        for line in ports_file.read_text().splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                if key == "API_PORT":
                    api_port = int(val)
                elif key == "WEB_PORT":
                    web_port = int(val)

    # Step 1: Build
    step = run_step("build", ["pnpm", "build"], project_dir, timeout=120, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Typecheck
    step = run_step("typecheck", ["pnpm", "typecheck"], project_dir, timeout=60, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 3: Lint — fail on any diagnostic output (errors, warnings, or info)
    step = run_step(
        "lint",
        ["pnpm", "lint"],
        project_dir,
        timeout=60,
        env=turbo_env,
        fail_on_output=[r"Found \d+ (error|warning|info)"],
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 4: Test
    step = run_step("test", ["pnpm", "test"], project_dir, timeout=120, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Detect whether this is a fullstack (with web) or API-only project
    has_web = (project_dir / "apps" / "web").is_dir()
    api_e2e_config = project_dir / "apps" / "api" / "playwright.config.ts"

    # Step 5: Install Playwright browsers (only needed for browser-based E2E)
    if has_web:
        playwright_config = project_dir / "apps" / "web" / "playwright.config.ts"
        if playwright_config.exists():
            step = run_step(
                "playwright install",
                ["pnpm", "--filter", "**/web", "exec", "playwright", "install", "chromium"],
                project_dir,
                timeout=120,
            )
            result.steps.append(step)

    # Step 5b: Ensure Postgres is running (may have been stopped if setup ran in a
    # separate process — e.g., the skill calls scaffold --setup then verify separately)
    compose_file = project_dir / "docker-compose.yml"
    if compose_file.exists():
        is_up = subprocess.run(
            ["docker", "compose", "ps", "--quiet", "postgres"],
            cwd=project_dir,
            capture_output=True,
            timeout=10,
        ).stdout.strip()
        if not is_up:
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=project_dir,
                capture_output=True,
                timeout=60,
            )
            for _ in range(15):
                ready = subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
                    cwd=project_dir,
                    capture_output=True,
                    timeout=5,
                )
                if ready.returncode == 0:
                    break
                time.sleep(2)

    # Step 6: Dev server smoke check
    dev_env = {
        **turbo_env,
        "PORT": str(api_port),
    }
    if has_web:
        dev_env["WEB_PORT"] = str(web_port)
        dev_env["VITE_API_PORT"] = str(api_port)

    import tempfile

    dev_stderr = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
    dev_proc = subprocess.Popen(
        ["pnpm", "exec", "turbo", "dev"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=dev_stderr,
        env=dev_env,
        start_new_session=True,
    )

    dev_pgid = os.getpgid(dev_proc.pid)
    atexit.register(_kill_process_group, dev_pgid)

    try:
        start = time.monotonic()
        api_up = wait_for_port(api_port, timeout=30)
        elapsed = time.monotonic() - start

        if not api_up:
            result.steps.append(
                StepResult("dev server (API)", False, elapsed, f"Port {api_port} not reachable")
            )
        elif not check_health(f"http://localhost:{api_port}/api/health"):
            result.steps.append(
                StepResult("dev server (API)", False, elapsed, "Health check failed")
            )
        else:
            result.steps.append(StepResult("dev server (API)", True, elapsed))

        web_up = False
        if has_web:
            web_up = wait_for_port(web_port, timeout=30)
            web_elapsed = time.monotonic() - start
            if not web_up:
                result.steps.append(
                    StepResult(
                        "dev server (web)", False, web_elapsed, f"Port {web_port} not reachable"
                    )
                )
            else:
                result.steps.append(StepResult("dev server (web)", True, web_elapsed))

        # Step 7: E2E tests (while dev server is running)
        # Build list of E2E targets — both web and API can have E2E tests
        e2e_targets: list[tuple[str, Path]] = []
        if has_web and web_up and (project_dir / "apps" / "web" / "playwright.config.ts").exists():
            e2e_targets.append(("e2e tests (web)", project_dir / "apps" / "web"))
        if api_up and api_e2e_config.exists():
            e2e_targets.append(("e2e tests (api)", project_dir / "apps" / "api"))

        if e2e_targets:
            e2e_env = {
                **os.environ,
                "E2E_API_PORT": str(api_port),
                "PLAYWRIGHT_SKIP_WEBSERVER": "1",
            }
            if has_web:
                e2e_env["E2E_WEB_PORT"] = str(web_port)

            import tempfile

            for e2e_name, e2e_dir in e2e_targets:
                e2e_start = time.monotonic()
                with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as e2e_log:
                    try:
                        e2e_proc = subprocess.run(
                            ["npx", "playwright", "test"],
                            cwd=e2e_dir,
                            stdout=e2e_log,
                            stderr=subprocess.STDOUT,
                            timeout=120,
                            env=e2e_env,
                        )
                        e2e_elapsed = time.monotonic() - e2e_start
                        if e2e_proc.returncode != 0:
                            e2e_log.seek(0)
                            error = e2e_log.read().strip()
                            if len(error) > 2000:
                                error = error[:2000] + "\n... (truncated)"
                            step = StepResult(e2e_name, False, e2e_elapsed, error)
                        else:
                            step = StepResult(e2e_name, True, e2e_elapsed)
                    except subprocess.TimeoutExpired:
                        e2e_elapsed = time.monotonic() - e2e_start
                        e2e_log.seek(0)
                        partial = e2e_log.read().strip()
                        error = "Timed out after 120s"
                        if partial:
                            error += f"\nPartial output:\n{partial[:1000]}"
                        step = StepResult(e2e_name, False, e2e_elapsed, error)
                result.steps.append(step)

        # Step 8: Clean exit check — send SIGINT and verify no error output
        dev_stderr.close()
        exit_step = _sigint_and_check(dev_proc, dev_pgid, dev_stderr.name)
        result.steps.append(exit_step)
    finally:
        try:
            pgid = os.getpgid(dev_proc.pid)
            _kill_process_group(pgid)
        except (ProcessLookupError, PermissionError):
            pass

    return result


# ---------------------------------------------------------------------------
# Python verification
# ---------------------------------------------------------------------------


def verify_python(
    project_dir: Path,
    api_port: int = 8000,
) -> VerifyResult:
    """Verify a Python (FastAPI/uv) scaffolded project.

    Assumes setup is already done (deps installed, docker running, db migrated).
    Reads ports from .env if available.
    """
    result = VerifyResult()

    # Read ports from .env (written by setup)
    dotenv = _read_dotenv(project_dir / ".env")
    if "API_PORT" in dotenv:
        api_port = int(dotenv["API_PORT"])

    # Step 1: Lint
    step = run_step("ruff check", ["uv", "run", "ruff", "check", "."], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Format check — fatal, templates must be formatted before verify
    step = run_step(
        "ruff format --check",
        ["uv", "run", "ruff", "format", "--check", "."],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 3: Test
    step = run_step("pytest", ["uv", "run", "pytest"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 3b: Ensure Postgres is running (may have been stopped if setup ran separately)
    compose_file = project_dir / "docker-compose.yml"
    if compose_file.exists():
        is_up = subprocess.run(
            ["docker", "compose", "ps", "--quiet", "postgres"],
            cwd=project_dir,
            capture_output=True,
            timeout=10,
        ).stdout.strip()
        if not is_up:
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=project_dir,
                capture_output=True,
                timeout=60,
            )
            for _ in range(15):
                ready = subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
                    cwd=project_dir,
                    capture_output=True,
                    timeout=5,
                )
                if ready.returncode == 0:
                    break
                time.sleep(2)

    # Step 4: Dev server smoke check
    api_app_dir = project_dir / "apps" / "api"
    if not api_app_dir.exists():
        # Flat project layout — run from root
        api_app_dir = project_dir

    dev_env = {**os.environ, "PORT": str(api_port)}
    if "DATABASE_URL" in dotenv:
        dev_env["DATABASE_URL"] = dotenv["DATABASE_URL"]
    import tempfile

    dev_stderr = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
    dev_proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.main:app", "--port", str(api_port)],
        cwd=api_app_dir,
        stdout=subprocess.DEVNULL,
        stderr=dev_stderr,
        env=dev_env,
        start_new_session=True,
    )

    dev_pgid = os.getpgid(dev_proc.pid)
    atexit.register(_kill_process_group, dev_pgid)

    try:
        start = time.monotonic()
        api_up = wait_for_port(api_port, timeout=15)
        elapsed = time.monotonic() - start

        if not api_up:
            result.steps.append(
                StepResult("dev server", False, elapsed, f"Port {api_port} not reachable")
            )
        elif not check_health(f"http://localhost:{api_port}/health"):
            result.steps.append(StepResult("dev server", False, elapsed, "Health check failed"))
        else:
            result.steps.append(StepResult("dev server", True, elapsed))

        # Step 5: Clean exit check
        dev_stderr.close()
        exit_step = _sigint_and_check(dev_proc, dev_pgid, dev_stderr.name)
        result.steps.append(exit_step)
    finally:
        try:
            pgid = os.getpgid(dev_proc.pid)
            _kill_process_group(pgid)
        except (ProcessLookupError, PermissionError):
            pass

    return result


# ---------------------------------------------------------------------------
# Fullstack Python verification (mixed: Python API + Node web)
# ---------------------------------------------------------------------------


def verify_fullstack_python(
    project_dir: Path,
    api_port: int = 8000,
    web_port: int = 3000,
) -> VerifyResult:
    """Verify a fullstack-python project (React frontend + FastAPI backend).

    Assumes setup is already done (deps installed, docker running, db migrated).
    Reads ports from .env if available.
    """
    result = VerifyResult()

    # Read ports from .env (written by setup)
    dotenv = _read_dotenv(project_dir / ".env")
    if "API_PORT" in dotenv:
        api_port = int(dotenv["API_PORT"])
    if "WEB_PORT" in dotenv:
        web_port = int(dotenv["WEB_PORT"])

    # Step 0: Verify justfile parses correctly (non-fatal — just may not be installed)
    step = run_step("just --summary", ["just", "--summary"], project_dir, timeout=10)
    result.steps.append(step)
    # Non-fatal — just may not be installed in the verify environment

    # Step 1: Python lint
    step = run_step("ruff check", ["uv", "run", "ruff", "check", "."], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Python format check — fatal, templates must be formatted before verify
    step = run_step(
        "ruff format --check",
        ["uv", "run", "ruff", "format", "--check", "."],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 3: Python tests
    step = run_step("pytest", ["uv", "run", "pytest"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 4: Biome check on web app — fail on any diagnostic output
    step = run_step(
        "biome check (web)",
        ["npx", "@biomejs/biome", "check", "--error-on-warnings", "apps/web/"],
        project_dir,
        timeout=60,
        fail_on_output=[r"Found \d+ (error|warning|info)"],
    )
    result.steps.append(step)
    # Non-fatal

    # Step 5: Web unit tests
    step = run_step(
        "vitest (web)",
        ["pnpm", "--dir", "apps/web", "run", "test"],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 6: Install Playwright browsers
    playwright_config = project_dir / "apps" / "web" / "playwright.config.ts"
    if playwright_config.exists():
        step = run_step(
            "playwright install",
            ["pnpm", "--dir", "apps/web", "exec", "playwright", "install", "chromium"],
            project_dir,
            timeout=120,
        )
        result.steps.append(step)

    # Step 7: Start dev servers via `just start` — the exact user-facing entry point.
    # This ensures the verified startup path is identical to what the developer runs,
    # catching issues like missing PATH entries, broken traps, or signal handling bugs
    # that only manifest through the justfile but not when processes are started directly.
    #
    # CI note: `just start` skips docker when DATABASE_URL is set in the environment,
    # so no docker port conflict occurs against a CI service container.
    import tempfile

    start_env = {**os.environ}
    if "DATABASE_URL" in dotenv:
        start_env["DATABASE_URL"] = dotenv["DATABASE_URL"]

    dev_stderr = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
    dev_proc = subprocess.Popen(
        ["just", "start"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=dev_stderr,
        env=start_env,
        start_new_session=True,
    )
    dev_pgid = os.getpgid(dev_proc.pid)
    atexit.register(_kill_process_group, dev_pgid)

    try:
        start = time.monotonic()
        # Generous timeout — just start has port discovery + optional docker overhead
        api_up = wait_for_port(api_port, timeout=60)
        elapsed = time.monotonic() - start

        if not api_up:
            result.steps.append(
                StepResult("dev server (API)", False, elapsed, f"Port {api_port} not reachable")
            )
        elif not check_health(f"http://localhost:{api_port}/api/health"):
            result.steps.append(
                StepResult("dev server (API)", False, elapsed, "Health check at /api/health failed")
            )
        else:
            result.steps.append(StepResult("dev server (API)", True, elapsed))

        web_up = wait_for_port(web_port, timeout=60)
        web_elapsed = time.monotonic() - start
        if not web_up:
            result.steps.append(
                StepResult("dev server (web)", False, web_elapsed, f"Port {web_port} not reachable")
            )
        else:
            # Health check through the Vite proxy
            if check_health(f"http://localhost:{web_port}/api/health"):
                result.steps.append(StepResult("dev server (web)", True, web_elapsed))
            else:
                result.steps.append(
                    StepResult(
                        "dev server (web)",
                        False,
                        web_elapsed,
                        "Proxy health check at web_port/api/health failed",
                    )
                )

        # Step 8: E2E tests (while dev servers are running)
        if api_up and web_up and playwright_config.exists():
            e2e_env = {
                **os.environ,
                "E2E_API_PORT": str(api_port),
                "E2E_WEB_PORT": str(web_port),
                "PLAYWRIGHT_SKIP_WEBSERVER": "1",
            }

            e2e_start = time.monotonic()
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as e2e_log:
                try:
                    e2e_proc = subprocess.run(
                        ["npx", "playwright", "test"],
                        cwd=project_dir / "apps" / "web",
                        stdout=e2e_log,
                        stderr=subprocess.STDOUT,
                        timeout=120,
                        env=e2e_env,
                    )
                    e2e_elapsed = time.monotonic() - e2e_start
                    if e2e_proc.returncode != 0:
                        e2e_log.seek(0)
                        error = e2e_log.read().strip()
                        if len(error) > 2000:
                            error = error[:2000] + "\n... (truncated)"
                        step = StepResult("e2e tests (web)", False, e2e_elapsed, error)
                    else:
                        step = StepResult("e2e tests (web)", True, e2e_elapsed)
                except subprocess.TimeoutExpired:
                    e2e_elapsed = time.monotonic() - e2e_start
                    e2e_log.seek(0)
                    partial = e2e_log.read().strip()
                    error = "Timed out after 120s"
                    if partial:
                        error += f"\nPartial output:\n{partial[:1000]}"
                    step = StepResult("e2e tests (web)", False, e2e_elapsed, error)
            result.steps.append(step)

        # Step 9: Clean exit — SIGINT just start and verify it shuts down cleanly
        dev_stderr.close()
        exit_step = _sigint_and_check(dev_proc, dev_pgid, dev_stderr.name)
        result.steps.append(exit_step)
    finally:
        try:
            _kill_process_group(dev_pgid)
        except (ProcessLookupError, PermissionError):
            pass

    return result


# ---------------------------------------------------------------------------
# Swift + TypeScript (swift-ts)
# ---------------------------------------------------------------------------


def verify_swift_ts(
    project_dir: Path,
    api_port: int = 3001,
) -> VerifyResult:
    """Verify a swift-ts project (TypeScript REST API + Xcode mobile placeholder).

    The Swift/Xcode side is not scaffolded — the user creates their Xcode project
    in apps/ios/ after scaffolding. Only the TypeScript API is verified here.
    """
    result = verify_node(
        project_dir,
        api_port=api_port,
        web_port=3000,  # unused — no web app
    )
    result.steps.append(
        StepResult(
            "swift: skipped",
            True,
            0,
            "Create your Xcode project in apps/ios/ — see apps/ios/README.md",
        )
    )
    return result


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def verify(
    project_dir: Path,
    api_port: int | None = None,
    web_port: int = 3000,
) -> VerifyResult:
    """Run quality checks against a scaffolded project.

    Assumes the project is already set up (deps installed, docker running,
    db pushed/migrated). Use ``setup_project()`` from ``scaffold.py`` for
    the setup phase.

    Detects the platform and dispatches to the appropriate verifier.

    Args:
        api_port: API server port. Defaults to 3001 for Node, 8000 for Python.
            Overridden by values in .env.ports / .env if present.
        web_port: Web server port (Node/fullstack-python, default 3000).
            Overridden by values in .env.ports / .env if present.
    """
    project_dir = Path(project_dir).resolve()
    platform = detect_platform(project_dir)

    if platform == "swift-ts":
        return verify_swift_ts(
            project_dir,
            api_port=api_port or 3001,
        )
    elif platform == "fullstack-python":
        return verify_fullstack_python(
            project_dir,
            api_port=api_port or 8000,
            web_port=web_port,
        )
    elif platform == "python":
        return verify_python(
            project_dir,
            api_port=api_port or 8000,
        )
    else:
        return verify_node(
            project_dir,
            api_port=api_port or 3001,
            web_port=web_port,
        )


def print_results(result: VerifyResult) -> None:
    """Print verification results as a formatted table."""
    name_width = max(len(s.name) for s in result.steps)

    print(f"\n{'Step':<{name_width}}  {'Time':>7}  Result")
    print(f"{'-' * name_width}  {'-' * 7}  {'-' * 10}")

    for s in result.steps:
        symbol = "\u2705" if s.passed else "\u274c"
        time_str = f"{s.duration_s:.1f}s"
        print(f"{s.name:<{name_width}}  {time_str:>7}  {symbol} {'pass' if s.passed else 'FAIL'}")
        if s.error:
            # Indent error output
            for line in s.error.split("\n")[:5]:
                print(f"  {line}")

    if result.passed:
        print("\nAll checks passed!")
    else:
        failed = [s.name for s in result.steps if not s.passed]
        print(f"\nFailed: {', '.join(failed)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a scaffolded project (quality checks only)"
    )
    parser.add_argument("project_dir", help="Path to the scaffolded project")
    parser.add_argument(
        "--api-port", type=int, default=None, help="API server port (default: auto-detect)"
    )
    parser.add_argument(
        "--web-port", type=int, default=3000, help="Web server port (default: 3000)"
    )
    args = parser.parse_args()

    result = verify(
        Path(args.project_dir),
        api_port=args.api_port,
        web_port=args.web_port,
    )
    print_results(result)

    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
