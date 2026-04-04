"""Verify a scaffolded project builds, typechecks, lints, and tests.

Runs the full verification suite in sequence: install, start services,
push DB schema, build, typecheck, lint, test, and dev server smoke check.
"""

from __future__ import annotations

import argparse
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
            error = proc.stderr.strip() or proc.stdout.strip()
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


def verify(
    project_dir: Path,
    api_port: int = 3001,
    web_port: int = 3000,
    skip_docker: bool = False,
) -> VerifyResult:
    """Run the full verification suite against a scaffolded project.

    Args:
        skip_docker: Skip docker compose up and pg_isready steps. Use when
            Postgres is already available (e.g., CI service container).
    """
    project_dir = Path(project_dir).resolve()
    result = VerifyResult()

    # Step 1: Install dependencies
    step = run_step("pnpm install", ["pnpm", "install"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 1b: Run project setup (port discovery + .env generation)
    # Only if the project has a setup script — scaffolded projects do
    setup_script = project_dir / "scripts" / "setup.ts"
    if setup_script.exists():
        step = run_step("setup", ["pnpm", "project:setup"], project_dir, timeout=30)
        result.steps.append(step)
        if not step.passed:
            return result

        # Read discovered ports so verify uses the same ones as the dev servers
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

    # Step 2: Start Postgres (skip if already available, e.g., CI service container)
    if not skip_docker:
        step = run_step("docker compose up", ["docker", "compose", "up", "-d"], project_dir, timeout=60)
        result.steps.append(step)
        if not step.passed:
            return result

        # Wait for Postgres health check
        step = run_step(
            "postgres health",
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
            project_dir,
            timeout=30,
        )
        # Retry a few times for Postgres startup
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
        if not step.passed:
            return result

    # Step 3: Push database schema
    step = run_step("db push", ["pnpm", "db:push"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 4: Build
    step = run_step("build", ["pnpm", "build"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 5: Typecheck
    step = run_step("typecheck", ["pnpm", "typecheck"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 6: Lint
    step = run_step("lint", ["pnpm", "lint"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7: Test
    step = run_step("test", ["pnpm", "test"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7b: Install Playwright browsers (before dev server, can be slow)
    playwright_config = project_dir / "apps" / "web" / "playwright.config.ts"
    if playwright_config.exists():
        step = run_step(
            "playwright install",
            ["pnpm", "--filter", "**/web", "exec", "playwright", "install", "chromium"],
            project_dir,
            timeout=120,
        )
        result.steps.append(step)
        # Non-fatal — E2E tests will fail but other checks can continue

    # Step 8: Dev server smoke check
    # Pass port env vars so the dev servers use the discovered ports
    import os
    dev_env = {
        **os.environ,
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
        start_new_session=True,  # Own process group so we can kill all children
    )
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
            # Run E2E tests against the already-running dev server.
            # Set E2E_WEB_PORT and E2E_API_PORT so Playwright config uses
            # the same ports, and PLAYWRIGHT_SKIP_WEBSERVER to bypass
            # Playwright's own server startup.
            import os
            e2e_env = {
                **os.environ,
                "E2E_WEB_PORT": str(web_port),
                "E2E_API_PORT": str(api_port),
                "PLAYWRIGHT_SKIP_WEBSERVER": "1",
            }
            # Run Playwright with output piped to a temp file to avoid
            # subprocess.PIPE blocking issues with Chromium's output volume.
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
        # Kill the entire process group (pnpm + turbo + vite + api child processes)
        import signal
        try:
            os.killpg(os.getpgid(dev_proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            dev_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(dev_proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    return result


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
    parser.add_argument("--api-port", type=int, default=3001, help="API server port (default: 3001)")
    parser.add_argument("--web-port", type=int, default=3000, help="Web server port (default: 3000)")
    parser.add_argument("--skip-docker", action="store_true", help="Skip docker compose (Postgres already available)")
    args = parser.parse_args()

    result = verify(Path(args.project_dir), api_port=args.api_port, web_port=args.web_port, skip_docker=args.skip_docker)
    print_results(result)

    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
