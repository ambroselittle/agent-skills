#!/usr/bin/env python3
"""Interactive scaffold E2E test runner.

Picks a template (or all), scaffolds it, and runs the full verify pipeline.
Requires: pnpm, node, and either Docker or DATABASE_URL env var.

Usage:
    python scripts/test-scaffolds.py                          # interactive picker
    python scripts/test-scaffolds.py fullstack-ts             # run specific template
    python scripts/test-scaffolds.py all                      # run all templates
    python scripts/test-scaffolds.py swift-ts --keep          # keep output in .eval-runs/
    python scripts/test-scaffolds.py swift-ts --keep /tmp/out # keep output at specific path
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Add create-repo to path so we can import its modules
CREATE_REPO_DIR = Path(__file__).resolve().parent.parent / "skills" / "create-repo"
sys.path.insert(0, str(CREATE_REPO_DIR))

from eval.run_eval import AVAILABLE_TEMPLATES, print_results, run_eval

# --- Terminal colors ---
_bold = "\033[1m"
_dim = "\033[2m"
_cyan = "\033[36m"
_green = "\033[32m"
_red = "\033[31m"
_yellow = "\033[33m"
_reset = "\033[0m"


def _header(text: str) -> None:
    width = 60
    print(f"\n{_bold}{_cyan}{'─' * width}{_reset}")
    print(f"{_bold}{_cyan}  {text}{_reset}")
    print(f"{_bold}{_cyan}{'─' * width}{_reset}")


def pick_template(templates: list[str]) -> list[str]:
    """Show a numbered menu and return selected template(s)."""
    _header("Scaffold E2E — pick a template")
    print()
    for i, t in enumerate(templates, 1):
        print(f"  {_cyan}[{i}]{_reset} {t}")
    print(f"  {_cyan}[{len(templates) + 1}]{_reset} all {_dim}(default){_reset}")
    print()

    try:
        choice = input(f"  Choice [{len(templates) + 1}]: ").strip()
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

    print(f"{_red}Invalid choice: {choice}{_reset}")
    sys.exit(1)


def main() -> None:
    templates = AVAILABLE_TEMPLATES
    verbose = "-v" in sys.argv

    # Parse --keep [optional-path] and -v out of argv; remainder is template name / "all"
    keep_output: Path | None = None
    raw_args = sys.argv[1:]
    filtered: list[str] = []
    i = 0
    while i < len(raw_args):
        a = raw_args[i]
        if a == "--keep":
            # Next arg is the output path (if it doesn't start with -)
            if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                keep_output = Path(raw_args[i + 1])
                i += 2
            else:
                keep_output = Path(".eval-runs") / "keep"
                i += 1
        elif a != "-v":
            filtered.append(a)
            i += 1
        else:
            i += 1
    args = filtered

    if keep_output and len(args) != 1:
        print(f"{_red}--keep requires exactly one template (not 'all'){_reset}")
        sys.exit(1)

    if args:
        arg = args[0]
        if arg == "all":
            selected = templates
        elif arg in templates:
            selected = [arg]
        else:
            print(f"{_red}Unknown template: {arg}{_reset}")
            print(f"Available: {', '.join(templates)}")
            sys.exit(1)
    else:
        selected = pick_template(templates)

    skip_docker = "DATABASE_URL" in os.environ
    passed_templates: list[str] = []
    failed_templates: list[str] = []

    total = len(selected)
    timings: list[tuple[str, float, bool]] = []
    run_start = time.monotonic()

    for i, template in enumerate(selected, 1):
        _header(f"[{i}/{total}] {template}")

        t0 = time.monotonic()
        result = run_eval(template, output_dir=keep_output, full=True, skip_docker=skip_docker)
        elapsed = time.monotonic() - t0

        if keep_output and result.passed:
            print(f"  {_dim}Output kept at: {keep_output}{_reset}")

        print_results(result, verbose=verbose)
        passed = result.passed
        timings.append((template, elapsed, passed))

        symbol = f"{_green}✓{_reset}" if passed else f"{_red}✗{_reset}"
        print(f"  {symbol} {_dim}{elapsed:.1f}s{_reset}")

        if passed:
            passed_templates.append(template)
        else:
            failed_templates.append(template)

    total_time = time.monotonic() - run_start

    # --- Summary ---
    print()
    print(f"{_bold}{'─' * 60}{_reset}")
    print(f"{_bold}  Summary{_reset} {_dim}({total_time:.0f}s){_reset}")
    print(f"{_bold}{'─' * 60}{_reset}")

    for name, elapsed, passed in timings:
        symbol = f"{_green}✓{_reset}" if passed else f"{_red}✗{_reset}"
        print(f"  {symbol} {name:<25} {_dim}{elapsed:.1f}s{_reset}")

    print()
    if not failed_templates:
        print(f"  {_bold}{_green}All {total} template(s) passed.{_reset}")
    else:
        print(
            f"  {_bold}{_red}{len(failed_templates)} failed{_reset}, "
            f"{len(passed_templates)} passed out of {total}"
        )

    print()

    if failed_templates:
        sys.exit(1)


if __name__ == "__main__":
    main()
