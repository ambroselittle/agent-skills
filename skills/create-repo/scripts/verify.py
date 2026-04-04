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


def run_step(name: str, cmd: list[str], cwd: Path, timeout: int = 300) -> StepResult:
    """Run a single verification step and return the result."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
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


def verify(project_dir: Path, api_port: int = 3001, web_port: int = 3000) -> VerifyResult:
    """Run the full verification suite against a scaffolded project."""
    project_dir = Path(project_dir).resolve()
    result = VerifyResult()

    # Step 1: Install dependencies
    step = run_step("pnpm install", ["pnpm", "install"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Start Postgres
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

    # Step 8: Dev server smoke check
    dev_proc = subprocess.Popen(
        ["pnpm", "dev"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
            step = run_step(
                "e2e tests",
                ["pnpm", "test:e2e"],
                project_dir,
                timeout=180,
            )
            result.steps.append(step)
    finally:
        dev_proc.terminate()
        try:
            dev_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            dev_proc.kill()

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
    args = parser.parse_args()

    result = verify(Path(args.project_dir), api_port=args.api_port, web_port=args.web_port)
    print_results(result)

    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
