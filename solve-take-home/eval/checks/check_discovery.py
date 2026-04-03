"""Discovery checks — can the skill find instructions in a take-home repo?

Tests the instruction discovery logic against fixtures. Given a fixture
directory, verifies that the expected instruction files are found and that
implicit specs (test stubs, TODOs, stack signals) are identified.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval.models import CheckResult


def check_discovery(fixture_dir: Path, rubric: dict) -> list[CheckResult]:
    """Run discovery checks against a fixture directory.

    Simulates what the skill's Phase 1 does: search for instruction files
    following the patterns in discovery-patterns.md.
    """
    checks: list[CheckResult] = []
    expected = rubric.get("discovery", {})

    # Check: primary instruction files are found
    primary_files = expected.get("primary_instruction_files", [])
    for filename in primary_files:
        path = fixture_dir / filename
        checks.append(CheckResult(
            f"discovery: found {filename}",
            path.exists(),
            None if path.exists() else f"Expected instruction file not found: {filename}",
        ))

    # Check: instruction files contain expected keywords
    expected_keywords = expected.get("instruction_keywords", [])
    if expected_keywords:
        all_instruction_text = ""
        for filename in primary_files:
            path = fixture_dir / filename
            if path.exists():
                all_instruction_text += path.read_text()

        for keyword in expected_keywords:
            found = keyword.lower() in all_instruction_text.lower()
            checks.append(CheckResult(
                f"discovery: instructions mention '{keyword}'",
                found,
                None if found else f"Keyword '{keyword}' not found in instruction files",
            ))

    # Check: test stubs are discovered
    expected_test_patterns = expected.get("test_file_patterns", [])
    for pattern in expected_test_patterns:
        matches = list(fixture_dir.glob(pattern))
        checks.append(CheckResult(
            f"discovery: test files match '{pattern}'",
            len(matches) > 0,
            None if matches else f"No files matching {pattern}",
        ))

    # Check: test stubs contain expected markers (test.todo, TODO, etc.)
    expected_test_markers = expected.get("test_markers", [])
    if expected_test_markers:
        all_test_text = ""
        for pattern in expected_test_patterns:
            for test_file in fixture_dir.glob(pattern):
                all_test_text += test_file.read_text()

        for marker in expected_test_markers:
            found = marker in all_test_text
            checks.append(CheckResult(
                f"discovery: test files contain '{marker}'",
                found,
                None if found else f"Marker '{marker}' not found in test files",
            ))

    # Check: stack signals are detected
    expected_stack_files = expected.get("stack_signal_files", [])
    for filename in expected_stack_files:
        path = fixture_dir / filename
        checks.append(CheckResult(
            f"discovery: stack signal '{filename}' exists",
            path.exists(),
            None if path.exists() else f"Expected stack signal file not found: {filename}",
        ))

    return checks
