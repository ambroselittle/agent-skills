"""Eval runner for solve-take-home skill.

Tests instruction discovery and brief synthesis against fixtures.
Verifies that the skill can find instructions, extract requirements,
and produce a complete brief.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.checks.check_brief import check_brief
from eval.checks.check_discovery import check_discovery
from eval.models import CheckResult, EvalResult

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = SKILL_ROOT / "fixtures"
RUBRIC_PATH = Path(__file__).resolve().parent / "rubric.json"


def load_rubric() -> dict:
    """Load the eval rubric."""
    return json.loads(RUBRIC_PATH.read_text())


def run_fixture_eval(fixture_name: str, fixture_dir: Path, rubric: dict) -> EvalResult:
    """Run all checks against a single fixture."""
    result = EvalResult(fixture=fixture_name)
    fixture_rubric = rubric.get("fixtures", {}).get(fixture_name, {})

    if not fixture_rubric:
        result.checks.append(CheckResult(
            "rubric",
            False,
            f"No rubric found for fixture '{fixture_name}'",
        ))
        return result

    # For repo-based fixtures (directories), run discovery + brief checks
    if fixture_dir.is_dir():
        discovery_checks = check_discovery(fixture_dir, fixture_rubric)
        result.checks.extend(discovery_checks)

        brief_checks = check_brief(fixture_dir, fixture_rubric)
        result.checks.extend(brief_checks)
    else:
        # For text-based fixtures (.md files), only run brief checks
        # Brief checks need a directory — use the file's parent and
        # handle the text file as if it were the README
        result.checks.append(CheckResult(
            "discovery: text-only fixture",
            True,
            "Text-only fixture — discovery phase would scaffold a repo",
        ))

        # For text fixtures, check that the text itself contains expected content
        text_rubric = fixture_rubric.get("brief", {})
        text = fixture_dir.read_text()

        for req in text_rubric.get("requirements", []):
            found = req.lower() in text.lower()
            result.checks.append(CheckResult(
                f"brief: requirement '{req}' is in text",
                found,
                None if found else f"Requirement '{req}' not found in text prompt",
            ))

        for term in text_rubric.get("acceptance_criteria_terms", []):
            found = term.lower() in text.lower()
            result.checks.append(CheckResult(
                f"brief: acceptance term '{term}' is in text",
                found,
                None if found else f"Term '{term}' not found in text prompt",
            ))

        time_limit = text_rubric.get("time_limit")
        if time_limit:
            found = time_limit.lower() in text.lower()
            result.checks.append(CheckResult(
                f"brief: time limit '{time_limit}' is detectable",
                found,
                None if found else f"Time limit not found in text",
            ))

        submission = text_rubric.get("submission_format")
        if submission:
            found = submission.lower() in text.lower()
            result.checks.append(CheckResult(
                f"brief: submission format '{submission}' is detectable",
                found,
                None if found else f"Submission format not found in text",
            ))

    return result


def discover_fixtures() -> list[tuple[str, Path]]:
    """Find all fixtures in the fixtures directory."""
    fixtures = []
    if not FIXTURES_DIR.exists():
        return fixtures

    for item in sorted(FIXTURES_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            fixtures.append((item.name, item))
        elif item.is_file() and item.suffix == ".md":
            # Text-only fixtures — use stem as name
            fixtures.append((item.stem, item))

    return fixtures


def print_results(result: EvalResult) -> None:
    """Print eval results as a formatted table."""
    if not result.checks:
        print(f"\nEval: {result.fixture} — no checks ran")
        return

    name_width = max(len(c.name) for c in result.checks)

    print(f"\nEval: {result.fixture}")
    print(f"{'Check':<{name_width}}  Result")
    print(f"{'-' * name_width}  {'-' * 10}")

    for c in result.checks:
        symbol = "\u2705" if c.passed else "\u274c"
        print(f"{c.name:<{name_width}}  {symbol} {'pass' if c.passed else 'FAIL'}")
        if c.detail and not c.passed:
            print(f"  {c.detail}")

    print(f"\n{result.pass_count}/{len(result.checks)} checks passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval runner for solve-take-home")
    parser.add_argument(
        "--fixture",
        default="all",
        help="Fixture to eval (default: all)",
    )
    args = parser.parse_args()

    rubric = load_rubric()
    fixtures = discover_fixtures()

    if args.fixture != "all":
        fixtures = [(name, path) for name, path in fixtures if name == args.fixture]
        if not fixtures:
            print(f"Fixture '{args.fixture}' not found")
            sys.exit(1)

    all_passed = True
    for name, path in fixtures:
        result = run_fixture_eval(name, path, rubric)
        print_results(result)
        if not result.passed:
            all_passed = False

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
