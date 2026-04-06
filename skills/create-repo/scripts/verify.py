"""Verify a scaffolded project builds, typechecks, lints, and tests.

Runs the full verification suite in sequence. Detects the project platform
(Node/Python) and runs the appropriate tool chain:
  - Node: pnpm install → prisma generate → biome → docker → db push → build → typecheck → lint → test → dev server → E2E
  - Python: uv sync → docker → alembic migrate → ruff → pytest → dev server
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


def run_step(name: str, cmd: list[str], cwd: Path, timeout: int = 300, env: dict | None = None) -> StepResult:
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
        return StepResult(name=name, passed=False, duration_s=elapsed, error=f"Timed out after {timeout}s")


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

    Returns 'python' if a root pyproject.toml exists, 'node' if package.json exists.
    Raises ValueError if neither is found.
    """
    if (project_dir / "pyproject.toml").exists():
        return "python"
    if (project_dir / "package.json").exists():
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

    # Step 7b: Install Playwright browsers
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
        "WEB_PORT": str(web_port),
        "VITE_API_PORT": str(api_port),
    }
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
        web_up = wait_for_port(web_port, timeout=30)
        elapsed = time.monotonic() - start

        if not api_up:
            result.steps.append(StepResult("dev server (API)", False, elapsed, f"Port {api_port} not reachable"))
        elif not check_health(f"http://localhost:{api_port}/api/health"):
            result.steps.append(StepResult("dev server (API)", False, elapsed, "Health check failed"))
        else:
            result.steps.append(StepResult("dev server (API)", True, elapsed))

        if not web_up:
            result.steps.append(StepResult("dev server (web)", False, elapsed, f"Port {web_port} not reachable"))
        else:
            result.steps.append(StepResult("dev server (web)", True, elapsed))

        # Step 9: E2E tests (while dev server is running)
        if api_up and web_up:
            e2e_env = {
                **os.environ,
                "E2E_WEB_PORT": str(web_port),
                "E2E_API_PORT": str(api_port),
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
                        step = StepResult("e2e tests", False, e2e_elapsed, error)
                    else:
                        step = StepResult("e2e tests", True, e2e_elapsed)
                except subprocess.TimeoutExpired:
                    e2e_elapsed = time.monotonic() - e2e_start
                    e2e_log.seek(0)
                    partial = e2e_log.read().strip()
                    error = f"Timed out after 120s"
                    if partial:
                        error += f"\nPartial output:\n{partial[:1000]}"
                    step = StepResult("e2e tests", False, e2e_elapsed, error)
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
    step = run_step("ruff format --check", ["uv", "run", "ruff", "format", "--check", "."], project_dir, timeout=60)
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
            result.steps.append(StepResult("dev server", False, elapsed, f"Port {api_port} not reachable"))
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
        web_port: Web server port (Node only, default 3000).
        skip_docker: Skip docker compose up and pg_isready steps. Use when
            Postgres is already available (e.g., CI service container).
    """
    project_dir = Path(project_dir).resolve()
    platform = detect_platform(project_dir)

    if platform == "python":
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
    parser.add_argument("--api-port", type=int, default=None, help="API server port (default: auto-detect)")
    parser.add_argument("--web-port", type=int, default=3000, help="Web server port (default: 3000)")
    parser.add_argument("--skip-docker", action="store_true", help="Skip docker compose (Postgres already available)")
    args = parser.parse_args()

    result = verify(Path(args.project_dir), api_port=args.api_port, web_port=args.web_port, skip_docker=args.skip_docker)
    print_results(result)

    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
