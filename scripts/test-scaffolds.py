#!/usr/bin/env python3
"""Interactive scaffold E2E test runner.

Picks a template (or all), scaffolds it, and runs the full verify pipeline.
Requires: pnpm, node, and either Docker or DATABASE_URL env var.

Usage:
    python scripts/test-scaffolds.py                 # interactive picker
    python scripts/test-scaffolds.py fullstack-ts    # run specific template
    python scripts/test-scaffolds.py all             # run all templates
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add create-repo to path so we can import its modules
CREATE_REPO_DIR = Path(__file__).resolve().parent.parent / "skills" / "create-repo"
sys.path.insert(0, str(CREATE_REPO_DIR))

from eval.run_eval import AVAILABLE_TEMPLATES, run_eval, print_results


def pick_template(templates: list[str]) -> list[str]:
    """Show a numbered menu and return selected template(s)."""
    print("\nScaffold E2E — pick a template:\n")
    for i, t in enumerate(templates, 1):
        print(f"  [{i}] {t}")
    print(f"  [{len(templates) + 1}] all (default)\n")

    try:
        choice = input(f"Choice [{len(templates) + 1}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(0)

    if not choice or choice == str(len(templates) + 1) or choice.lower() == "all":
        return templates

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(templates):
            return [templates[idx]]
    except ValueError:
        # Maybe they typed the name directly
        if choice in templates:
            return [choice]

    print(f"Invalid choice: {choice}")
    sys.exit(1)


def main() -> None:
    templates = AVAILABLE_TEMPLATES

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "all":
            selected = templates
        elif arg in templates:
            selected = [arg]
        else:
            print(f"Unknown template: {arg}")
            print(f"Available: {', '.join(templates)}")
            sys.exit(1)
    else:
        selected = pick_template(templates)

    skip_docker = "DATABASE_URL" in os.environ
    all_passed = True

    for template in selected:
        print(f"\n{'='*60}")
        print(f"Testing scaffold: {template}")
        print(f"{'='*60}")

        result = run_eval(template, full=True, skip_docker=skip_docker)
        print_results(result)

        if not result.passed:
            all_passed = False

    print(f"\n{'='*60}")
    if all_passed:
        print(f"All {len(selected)} template(s) passed.")
    else:
        print(f"Some templates failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
