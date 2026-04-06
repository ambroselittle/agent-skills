"""Eval runner for create-repo scaffolded projects.

Runs the full pipeline (scaffold with test versions) and then checks
the output for structural correctness, configuration quality, and
completeness. Eval outputs go to .eval-runs/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path so we can import scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.checks.check_structure import check_structure
from eval.models import CheckResult, EvalResult
from scripts.scaffold import scaffold
from scripts.verify import verify as run_verify

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_RUNS_DIR = PROJECT_ROOT / ".eval-runs"
VERSION_CACHE_DIR = Path.home() / ".agent-skills" / ".version-cache"

# Default TTL for cached versions (24 hours)
VERSION_CACHE_TTL_SECONDS = 86400

# Fallback versions for eval — used when no cache exists and --fresh is not set
FALLBACK_VERSIONS = {
    "react": "19.1.0",
    "react_dom": "19.1.0",
    "typescript": "5.8.3",
    "vite": "6.3.0",
    "vitest": "3.1.1",
    "hono": "4.7.6",
    "hono_node_server": "1.19.12",
    "tailwindcss": "4.1.3",
    "tailwindcss_vite": "4.1.3",
    "prisma": "7.5.0",
    "prisma_client": "7.5.0",
    "prisma_adapter_pg": "7.5.0",
    "biomejs_biome": "2.0.0",
    "trpc_server": "11.1.0",
    "trpc_client": "11.1.0",
    "trpc_react_query": "11.1.0",
    "hono_trpc_server": "0.3.2",
    "tanstack_react_query": "5.74.4",
    "types_react": "19.1.2",
    "types_react_dom": "19.1.2",
    "vitejs_plugin_react": "4.4.1",
    "playwright": "1.59.1",
    "playwright_test": "1.59.1",
    "jsdom": "25.0.1",
    "testing_library_react": "16.3.2",
    "testing_library_jest_dom": "6.9.1",
    "dotenv": "17.4.1",
    "pnpm": "10.33.0",
    # GraphQL stack
    "graphql": "16.13.2",
    "graphql_yoga": "5.21.0",
    "pothos_core": "4.12.0",
    "apollo_client": "3.14.1",
    "graphql_codegen_cli": "6.2.1",
    "graphql_codegen_typescript": "5.0.9",
    "graphql_codegen_typescript_operations": "5.0.9",
    "graphql_codegen_typescript_react_apollo": "4.4.1",
    # Python packages (api-python, fullstack-python)
    "fastapi": "0.115.12",
    "sqlmodel": "0.0.24",
    "sqlalchemy": "2.0.40",
    "pydantic": "2.11.4",
    "uvicorn": "0.34.3",
    "alembic": "1.15.2",
    "pytest": "8.4.1",
    "httpx": "0.28.1",
    "ruff": "0.11.12",
}


def get_cached_versions(template: str) -> dict | None:
    """Load cached versions if they exist and are fresh enough."""
    cache_file = VERSION_CACHE_DIR / f"{template}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > VERSION_CACHE_TTL_SECONDS:
            return None
        return data.get("versions")
    except (json.JSONDecodeError, KeyError):
        return None


def save_version_cache(template: str, versions: dict) -> None:
    """Save resolved versions to cache with a timestamp."""
    VERSION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = VERSION_CACHE_DIR / f"{template}.json"
    cache_file.write_text(json.dumps({
        "cached_at": time.time(),
        "cached_at_human": datetime.now(timezone.utc).isoformat(),
        "template": template,
        "versions": versions,
    }, indent=2))


def get_versions(template: str) -> dict:
    """Get versions for a template, using cache if fresh.

    Returns cached versions if available and within TTL,
    otherwise returns fallback versions.
    """
    cached = get_cached_versions(template)
    if cached:
        return cached
    return FALLBACK_VERSIONS


def run_eval(
    template: str,
    output_dir: Path | None = None,
    full: bool = False,
    skip_docker: bool = False,
) -> EvalResult:
    """Run eval for a template.

    Scaffolds a test project and runs structural checks. When full=True,
    also runs the complete verification pipeline (install, build, typecheck,
    lint, test, dev server, E2E).

    Args:
        full: Run the full verification pipeline after structural checks.
        skip_docker: Skip docker compose steps (Postgres already available).
    """
    result = EvalResult(template=template)
    versions = get_versions(template)

    # Determine output directory
    if output_dir is None:
        EVAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        project_dir = EVAL_RUNS_DIR / f"{template}-{timestamp}" / "eval-project"
    else:
        project_dir = output_dir

    # Clean up if it exists from a previous run
    if project_dir.exists():
        shutil.rmtree(project_dir)

    # Step 1: Scaffold
    try:
        scaffold("eval-project", template, versions, project_dir)
        result.checks.append(CheckResult("scaffold", True))
    except Exception as e:
        result.checks.append(CheckResult("scaffold", False, str(e)))
        return result  # Can't continue without scaffold

    # Step 2: Structural checks
    structure_checks = check_structure(project_dir, template)
    result.checks.extend(structure_checks)

    # Step 3: Full verification (optional — install, build, test, etc.)
    if full:
        if not result.passed:
            result.checks.append(CheckResult(
                "verify (skipped)", False, "Structural checks failed — skipping verification",
            ))
            return result

        # In CI (skip_docker=True), write .env files before verify since
        # pnpm setup won't discover ports (Postgres is a service container).
        # Locally, verify.py runs pnpm setup which handles .env generation.
        if skip_docker:
            _write_ci_env_files(project_dir)

        try:
            verify_result = run_verify(
                project_dir,
                skip_docker=skip_docker,
            )
            for step in verify_result.steps:
                result.checks.append(CheckResult(
                    f"verify: {step.name}",
                    step.passed,
                    step.error,
                ))
        finally:
            # Clean up Docker resources if we started them
            if not skip_docker:
                subprocess.run(
                    ["docker", "compose", "down", "-v", "--remove-orphans"],
                    cwd=project_dir,
                    capture_output=True,
                    timeout=30,
                )

            # Clean up the eval run directory to avoid accumulating node_modules
            if output_dir is None and project_dir.exists():
                shutil.rmtree(project_dir.parent, ignore_errors=True)

    return result


def _write_ci_env_files(project_dir: Path) -> None:
    """Write .env files for CI where Postgres is a service container.

    Uses DATABASE_URL from the environment. Detects platform and writes
    the appropriate .env files.
    """
    import os

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/eval_project_dev",
    )

    is_python = (project_dir / "pyproject.toml").exists()

    if is_python:
        # Python projects: root .env + apps/api/.env
        (project_dir / ".env").write_text(f"DATABASE_URL={db_url}\n")
        api_dir = project_dir / "apps" / "api"
        if api_dir.exists():
            (api_dir / ".env").write_text(f"DATABASE_URL={db_url}\n")
    else:
        # Node projects: root + per-package .env files
        (project_dir / ".env").write_text(
            f"DATABASE_URL={db_url}\n"
            f"DB_PORT=5432\n"
            f"API_PORT=3001\n"
            f"WEB_PORT=3000\n"
        )

        db_dir = project_dir / "packages" / "db"
        if db_dir.exists():
            (db_dir / ".env").write_text(f"DATABASE_URL={db_url}\n")

        api_dir = project_dir / "apps" / "api"
        if api_dir.exists():
            (api_dir / ".env").write_text(f"DATABASE_URL={db_url}\nPORT=3001\n")

        web_dir = project_dir / "apps" / "web"
        if web_dir.exists():
            (web_dir / ".env").write_text(f"WEB_PORT=3000\nVITE_API_PORT=3001\n")


def print_results(result: EvalResult) -> None:
    """Print eval results as a formatted table."""
    name_width = max(len(c.name) for c in result.checks)

    print(f"\nEval: {result.template}")
    print(f"{'Check':<{name_width}}  Result")
    print(f"{'-' * name_width}  {'-' * 10}")

    for c in result.checks:
        symbol = "\u2705" if c.passed else "\u274c"
        print(f"{c.name:<{name_width}}  {symbol} {'pass' if c.passed else 'FAIL'}")
        if c.detail:
            print(f"  {c.detail}")

    print(f"\n{result.pass_count}/{len(result.checks)} checks passed")


AVAILABLE_TEMPLATES = ["fullstack-ts", "fullstack-graphql", "api-python"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval runner for create-repo")
    parser.add_argument(
        "--template",
        default="all",
        help="Template to eval (default: all implemented templates)",
    )
    parser.add_argument(
        "--output",
        help="Output directory (default: .eval-runs/)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full verification (install, build, test) — requires pnpm, node, and Postgres",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip docker compose (Postgres already available, e.g., CI)",
    )
    args = parser.parse_args()

    templates = AVAILABLE_TEMPLATES if args.template == "all" else [args.template]
    all_passed = True

    for template in templates:
        output = Path(args.output) if args.output else None
        result = run_eval(template, output, full=args.full, skip_docker=args.skip_docker)
        print_results(result)
        if not result.passed:
            all_passed = False

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
