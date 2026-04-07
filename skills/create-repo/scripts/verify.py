"""Verify a scaffolded project builds, typechecks, lints, and tests.

Runs the full verification suite in sequence. Detects the project platform
(Node/Python/fullstack-python) and runs the appropriate tool chain.
"""

from __future__ import annotations

import argparse
import atexit
import os
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
    name: str, cmd: list[str], cwd: Path, timeout: int = 300, env: dict | None = None
) -> StepResult:
    """Run a single verification step and return the result."""
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
        if proc.returncode != 0:
            # Combine stderr and stdout — tools like turbo put their own
            # error wrapper on stderr while the actual child error is on stdout.
            parts = [s for s in (proc.stderr.strip(), proc.stdout.strip()) if s]
            error = "\n".join(parts) if parts else f"Exit code {proc.returncode}"
            # Truncate long error output
            if len(error) > 2000:
                error = error[:2000] + "\n... (truncated)"
            return StepResult(name=name, passed=False, duration_s=elapsed, error=error)
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


def detect_platform(project_dir: Path) -> str:
    """Detect the project platform from its files.

    Returns 'swift-ts' if package.json and apps/mobile/Package.swift both exist,
    'fullstack-python' if both pyproject.toml and package.json exist,
    'python' if only pyproject.toml, 'node' if only package.json.
    Raises ValueError if neither is found.
    """
    has_pyproject = (project_dir / "pyproject.toml").exists()
    has_package_json = (project_dir / "package.json").exists()
    has_mobile_project = (project_dir / "apps" / "mobile" / "Package.swift").exists()
    if has_package_json and has_mobile_project:
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


def _start_postgres(project_dir: Path, result: VerifyResult, skip_docker: bool) -> bool:
    """Start Postgres via docker compose if needed. Returns True if ready."""
    if skip_docker:
        return True

    step = run_step("docker compose up", ["docker", "compose", "up", "-d"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return False

    # Wait for Postgres health check
    step = run_step(
        "postgres health",
        ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
        project_dir,
        timeout=30,
    )
    for _ in range(5):
        if step.passed:
            break
        time.sleep(2)
        step = run_step(
            "postgres health",
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
            project_dir,
            timeout=10,
        )
    result.steps.append(step)
    return step.passed


# ---------------------------------------------------------------------------
# Node verification
# ---------------------------------------------------------------------------


def verify_node(
    project_dir: Path,
    api_port: int = 3001,
    web_port: int = 3000,
    skip_docker: bool = False,
) -> VerifyResult:
    """Verify a Node/TypeScript scaffolded project."""
    result = VerifyResult()

    # Force a project-local turbo cache to prevent cross-worktree cache
    # pollution (turbo matches on content hash, not path, so eval runs in
    # different worktrees share stale cached logs with wrong absolute paths).
    turbo_env = {**os.environ, "TURBO_CACHE_DIR": str(project_dir / ".turbo")}

    # Step 1: Install dependencies
    step = run_step("pnpm install", ["pnpm", "install"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 1b: Run project setup (port discovery + .env generation)
    setup_script = project_dir / "scripts" / "setup.ts"
    if setup_script.exists() and not skip_docker:
        step = run_step("setup", ["pnpm", "project:setup"], project_dir, timeout=30)
        result.steps.append(step)
        if not step.passed:
            return result

        ports_file = project_dir / ".env.ports"
        if ports_file.exists():
            for line in ports_file.read_text().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key == "API_PORT":
                        api_port = int(val)
                    elif key == "WEB_PORT":
                        web_port = int(val)

    # Step 1c: Generate Prisma client + barrel exports
    step = run_step(
        "prisma generate",
        ["pnpm", "--filter", "**/db", "run", "generate"],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 1d: Auto-format with Biome (fix formatting drift from generation)
    step = run_step("biome format", ["pnpm", "lint:fix"], project_dir, timeout=60)
    result.steps.append(step)
    # Non-fatal — continue even if format step fails

    # Step 2: Start Postgres
    if not _start_postgres(project_dir, result, skip_docker):
        return result

    # Step 3: Push database schema
    step = run_step("db push", ["pnpm", "db:push"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 3b: Seed database
    step = run_step("db seed", ["pnpm", "db:seed"], project_dir, timeout=60)
    result.steps.append(step)
    # Non-fatal — tests can run without seed data

    # Step 4: Build
    step = run_step("build", ["pnpm", "build"], project_dir, timeout=120, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 5: Typecheck
    step = run_step("typecheck", ["pnpm", "typecheck"], project_dir, timeout=60, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 6: Lint
    step = run_step("lint", ["pnpm", "lint"], project_dir, timeout=60, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7: Test
    step = run_step("test", ["pnpm", "test"], project_dir, timeout=120, env=turbo_env)
    result.steps.append(step)
    if not step.passed:
        return result

    # Detect whether this is a fullstack (with web) or API-only project
    has_web = (project_dir / "apps" / "web").is_dir()
    api_e2e_config = project_dir / "apps" / "api" / "playwright.config.ts"

    # Step 7b: Install Playwright browsers (only needed for browser-based E2E)
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

    # Step 8: Dev server smoke check
    dev_env = {
        **turbo_env,
        "PORT": str(api_port),
    }
    if has_web:
        dev_env["WEB_PORT"] = str(web_port)
        dev_env["VITE_API_PORT"] = str(api_port)

    dev_proc = subprocess.Popen(
        ["pnpm", "dev"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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

        # Step 9: E2E tests (while dev server is running)
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
    skip_docker: bool = False,
) -> VerifyResult:
    """Verify a Python (FastAPI/uv) scaffolded project."""
    result = VerifyResult()

    # Step 1: Install dependencies
    # Use Python 3.13 if available — 3.14 lacks prebuilt wheels for many
    # packages (pydantic-core, etc.), causing slow Rust compilation failures.
    uv_sync_cmd = ["uv", "sync"]
    try:
        import subprocess as _sp

        _sp.run(["uv", "python", "find", "3.13"], capture_output=True, check=True)
        uv_sync_cmd = ["uv", "sync", "--python", "3.13"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # Fall back to default Python
    step = run_step("uv sync", uv_sync_cmd, project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Start Postgres
    if not _start_postgres(project_dir, result, skip_docker):
        return result

    # Step 3: Run Alembic migrations (if alembic.ini exists in any app)
    alembic_dirs = list(project_dir.glob("apps/*/alembic.ini"))
    for alembic_ini in alembic_dirs:
        app_dir = alembic_ini.parent
        app_name = app_dir.name
        step = run_step(
            f"alembic upgrade ({app_name})",
            ["uv", "run", "alembic", "upgrade", "head"],
            app_dir,
            timeout=300,  # May compile native deps (e.g., pydantic-core) on newer Python
        )
        result.steps.append(step)
        if not step.passed:
            return result

    # Step 4: Lint
    step = run_step("ruff check", ["uv", "run", "ruff", "check", "."], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 5: Format check
    step = run_step(
        "ruff format --check",
        ["uv", "run", "ruff", "format", "--check", "."],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    # Non-fatal — continue even if format check fails

    # Step 6: Test
    step = run_step("pytest", ["uv", "run", "pytest"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7: Dev server smoke check
    api_app_dir = project_dir / "apps" / "api"
    if not api_app_dir.exists():
        # Flat project layout — run from root
        api_app_dir = project_dir

    dev_env = {**os.environ, "PORT": str(api_port)}
    dev_proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.main:app", "--port", str(api_port)],
        cwd=api_app_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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
    skip_docker: bool = False,
) -> VerifyResult:
    """Verify a fullstack-python project (React frontend + FastAPI backend)."""
    result = VerifyResult()

    # Step 0: Verify justfile parses correctly (non-fatal — just may not be installed)
    step = run_step("just --summary", ["just", "--summary"], project_dir, timeout=10)
    result.steps.append(step)
    # Non-fatal — just may not be installed in the verify environment

    # Step 1a: Install Python dependencies
    uv_sync_cmd = ["uv", "sync"]
    try:
        import subprocess as _sp

        _sp.run(["uv", "python", "find", "3.13"], capture_output=True, check=True)
        uv_sync_cmd = ["uv", "sync", "--python", "3.13"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    step = run_step("uv sync", uv_sync_cmd, project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 1b: Install web dependencies
    step = run_step(
        "pnpm install (web)",
        ["pnpm", "install", "--dir", "apps/web"],
        project_dir,
        timeout=120,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Start Postgres
    if not _start_postgres(project_dir, result, skip_docker):
        return result

    # Step 3: Run Alembic migrations
    alembic_dirs = list(project_dir.glob("apps/*/alembic.ini"))
    for alembic_ini in alembic_dirs:
        app_dir = alembic_ini.parent
        app_name = app_dir.name
        step = run_step(
            f"alembic upgrade ({app_name})",
            ["uv", "run", "alembic", "upgrade", "head"],
            app_dir,
            timeout=300,
        )
        result.steps.append(step)
        if not step.passed:
            return result

    # Step 4: Python lint
    step = run_step("ruff check", ["uv", "run", "ruff", "check", "."], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 5: Python format check (non-fatal)
    step = run_step(
        "ruff format --check",
        ["uv", "run", "ruff", "format", "--check", "."],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)

    # Step 6: Python tests
    step = run_step("pytest", ["uv", "run", "pytest"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7: Biome check on web app
    step = run_step(
        "biome check (web)",
        ["npx", "@biomejs/biome", "check", "apps/web/"],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    # Non-fatal

    # Step 7b: Web unit tests
    step = run_step(
        "vitest (web)",
        ["pnpm", "--dir", "apps/web", "run", "test"],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7c: Install Playwright browsers
    playwright_config = project_dir / "apps" / "web" / "playwright.config.ts"
    if playwright_config.exists():
        step = run_step(
            "playwright install",
            ["pnpm", "--dir", "apps/web", "exec", "playwright", "install", "chromium"],
            project_dir,
            timeout=120,
        )
        result.steps.append(step)

    # Step 8: Start both dev servers
    api_app_dir = project_dir / "apps" / "api"
    dev_env = {**os.environ, "PORT": str(api_port)}

    api_proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.main:app", "--port", str(api_port)],
        cwd=api_app_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=dev_env,
        start_new_session=True,
    )
    api_pgid = os.getpgid(api_proc.pid)
    atexit.register(_kill_process_group, api_pgid)

    web_env = {
        **os.environ,
        "WEB_PORT": str(web_port),
        "VITE_API_PORT": str(api_port),
    }
    web_proc = subprocess.Popen(
        ["pnpm", "dev"],
        cwd=project_dir / "apps" / "web",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=web_env,
        start_new_session=True,
    )
    web_pgid = os.getpgid(web_proc.pid)
    atexit.register(_kill_process_group, web_pgid)

    try:
        start = time.monotonic()
        api_up = wait_for_port(api_port, timeout=15)
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

        web_up = wait_for_port(web_port, timeout=30)
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

        # Step 9: E2E tests (while dev servers are running)
        if api_up and web_up and playwright_config.exists():
            e2e_env = {
                **os.environ,
                "E2E_API_PORT": str(api_port),
                "E2E_WEB_PORT": str(web_port),
                "PLAYWRIGHT_SKIP_WEBSERVER": "1",
            }

            import tempfile

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
    finally:
        for pgid in (api_pgid, web_pgid):
            try:
                _kill_process_group(pgid)
            except (ProcessLookupError, PermissionError):
                pass

    return result


# ---------------------------------------------------------------------------
# Swift + TypeScript (swift-ts)
# ---------------------------------------------------------------------------


def verify_swift_ts(
    project_dir: Path,
    api_port: int = 3001,
    skip_docker: bool = False,
) -> VerifyResult:
    """Verify a swift-ts project (Swift multiplatform + TypeScript REST API).

    Runs the standard Node pipeline for the TypeScript API side, then
    optionally runs xcodebuild for the Swift side (macOS only).
    On non-macOS platforms, Swift verification is skipped with a message.
    """
    result = verify_node(
        project_dir,
        api_port=api_port,
        web_port=3000,  # unused — no web app
        skip_docker=skip_docker,
    )

    # Swift-side verification (macOS only)
    import sys

    if sys.platform != "darwin":
        result.steps.append(StepResult(
            "swift: skipped",
            "(not macOS)",
            True,
            0,
        ))
        return result

    mobile_dir = project_dir / "apps" / "mobile"
    if not mobile_dir.exists():
        result.steps.append(StepResult(
            "swift: skipped",
            "apps/mobile/ not found",
            True,
            0,
        ))
        return result

    # Check if full Xcode (not just CLT) is available.
    # xcodebuild exists in Command Line Tools but can't build iOS apps.
    import shutil
    import subprocess as _sp

    has_full_xcode = False
    if shutil.which("xcodebuild"):
        try:
            out = _sp.run(
                ["xcode-select", "-p"],
                capture_output=True, text=True, timeout=5,
            )
            # Full Xcode: /Applications/Xcode.app/Contents/Developer
            # CLT only:   /Library/Developer/CommandLineTools
            has_full_xcode = out.returncode == 0 and "Xcode.app" in out.stdout
        except Exception:
            pass

    if not has_full_xcode:
        result.steps.append(StepResult(
            "swift: skipped",
            "Full Xcode not found (Command Line Tools alone can't build iOS apps).",
            True,
            0,
        ))
        return result

    scheme = _detect_scheme(mobile_dir)

    # xcodebuild build (generic iOS Simulator — no specific device needed)
    step = run_step(
        "xcodebuild build",
        [
            "xcodebuild", "build",
            "-scheme", scheme,
            "-destination", "generic/platform=iOS Simulator",
            "-skipPackagePluginValidation",
            "CODE_SIGNING_ALLOWED=NO",
        ],
        mobile_dir,
        timeout=300,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # xcodebuild test — needs a concrete simulator.
    # Find the first available iPhone simulator.
    sim_dest = _find_ios_simulator()
    if not sim_dest:
        result.steps.append(StepResult(
            "xcodebuild test: skipped",
            "No iOS Simulator found. Install an iOS Simulator runtime in Xcode.",
            True,
            0,
        ))
        return result

    step = run_step(
        "xcodebuild test",
        [
            "xcodebuild", "test",
            "-scheme", scheme,
            "-destination", sim_dest,
            "-skipPackagePluginValidation",
            "CODE_SIGNING_ALLOWED=NO",
        ],
        mobile_dir,
        timeout=300,
    )
    result.steps.append(step)

    return result


def _find_ios_simulator() -> str | None:
    """Find an available iOS Simulator destination string for xcodebuild."""
    import json
    import subprocess as _sp

    try:
        out = _sp.run(
            ["xcrun", "simctl", "list", "devices", "available", "-j"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        for runtime, devices in data.get("devices", {}).items():
            if "iOS" not in runtime:
                continue
            for dev in devices:
                if "iPhone" in dev.get("name", ""):
                    return f"platform=iOS Simulator,id={dev['udid']}"
    except Exception:
        pass
    return None


def _detect_scheme(mobile_dir: Path) -> str:
    """Detect the Xcode scheme name from Package.swift or .xcodeproj."""
    import re

    package_swift = mobile_dir / "Package.swift"
    if package_swift.exists():
        # Extract package name from: name: "MyApp"
        match = re.search(r'name:\s*"([^"]+)"', package_swift.read_text())
        if match:
            return match.group(1).strip()
    # Fallback: look for .xcodeproj
    for p in mobile_dir.iterdir():
        if p.suffix == ".xcodeproj":
            return p.stem
    return "App"


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def verify(
    project_dir: Path,
    api_port: int | None = None,
    web_port: int = 3000,
    skip_docker: bool = False,
) -> VerifyResult:
    """Run the full verification suite against a scaffolded project.

    Detects the platform and dispatches to the appropriate verifier.

    Args:
        api_port: API server port. Defaults to 3001 for Node, 8000 for Python.
        web_port: Web server port (Node/fullstack-python, default 3000).
        skip_docker: Skip docker compose up and pg_isready steps. Use when
            Postgres is already available (e.g., CI service container).
    """
    project_dir = Path(project_dir).resolve()
    platform = detect_platform(project_dir)

    if platform == "swift-ts":
        return verify_swift_ts(
            project_dir,
            api_port=api_port or 3001,
            skip_docker=skip_docker,
        )
    elif platform == "fullstack-python":
        return verify_fullstack_python(
            project_dir,
            api_port=api_port or 8000,
            web_port=web_port,
            skip_docker=skip_docker,
        )
    elif platform == "python":
        return verify_python(
            project_dir,
            api_port=api_port or 8000,
            skip_docker=skip_docker,
        )
    else:
        return verify_node(
            project_dir,
            api_port=api_port or 3001,
            web_port=web_port,
            skip_docker=skip_docker,
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
    parser = argparse.ArgumentParser(description="Verify a scaffolded project")
    parser.add_argument("project_dir", help="Path to the scaffolded project")
    parser.add_argument(
        "--api-port", type=int, default=None, help="API server port (default: auto-detect)"
    )
    parser.add_argument(
        "--web-port", type=int, default=3000, help="Web server port (default: 3000)"
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip docker compose (Postgres already available)",
    )
    args = parser.parse_args()

    result = verify(
        Path(args.project_dir),
        api_port=args.api_port,
        web_port=args.web_port,
        skip_docker=args.skip_docker,
    )
    print_results(result)

    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
