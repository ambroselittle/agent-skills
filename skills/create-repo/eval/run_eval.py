"""Eval runner for create-repo scaffolded projects.

Runs the full pipeline (scaffold with test versions) and then checks
the output for structural correctness, configuration quality, and
completeness. Eval outputs go to .eval-runs/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path so we can import scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.checks.check_structure import check_structure
from eval.models import CheckResult, EvalResult
from scripts.scaffold import scaffold

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
    "prisma": "6.6.0",
    "prisma_client": "6.6.0",
    "prisma_adapter_pg": "6.6.0",
    "biomejs_biome": "1.9.4",
    "trpc_server": "11.1.0",
    "trpc_client": "11.1.0",
    "trpc_react_query": "11.1.0",
    "hono_trpc_server": "0.3.2",
    "tanstack_react_query": "5.74.4",
    "types_react": "19.1.2",
    "types_react_dom": "19.1.2",
    "vitejs_plugin_react": "4.4.1",
    "playwright": "1.52.0",
    "playwright_test": "1.52.0",
    "pnpm": "10.33.0",
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


def run_eval(template: str, output_dir: Path | None = None) -> EvalResult:
    """Run the full eval for a template.

    Scaffolds a test project and runs all structural checks against it.
    Eval output goes to .eval-runs/<template>-<timestamp>/.
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

    return result


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


AVAILABLE_TEMPLATES = ["fullstack-ts"]


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
    args = parser.parse_args()

    templates = AVAILABLE_TEMPLATES if args.template == "all" else [args.template]
    all_passed = True

    for template in templates:
        output = Path(args.output) if args.output else None
        result = run_eval(template, output)
        print_results(result)
        if not result.passed:
            all_passed = False

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
