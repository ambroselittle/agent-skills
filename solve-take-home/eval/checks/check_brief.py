"""Brief synthesis checks — does the extracted brief cover all requirements?

Given a fixture's instruction text and the rubric's expected requirements,
verifies that a brief extraction would capture all the key elements.
This simulates what the skill does when it reads instructions and produces
a structured brief.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval.models import CheckResult

# Base names and extensions from discovery-patterns.md
_BASE_NAMES = [
    "README", "INSTRUCTIONS", "PROMPT", "CHALLENGE",
    "ASSIGNMENT", "REQUIREMENTS", "SPEC", "TODO",
]
_EXTENSIONS = [".md", ".txt", ".html", ".rst", ".adoc", ""]

INSTRUCTION_FILES = [
    f"{name}{ext}" for name in _BASE_NAMES for ext in _EXTENSIONS
]


def _collect_instruction_text(source: Path) -> str:
    """Collect instruction text from a directory or a single file.

    For directories, reads all known instruction files.
    For files, reads the file directly.
    """
    if source.is_file():
        return source.read_text()

    text = ""
    for filename in INSTRUCTION_FILES:
        path = source / filename
        if path.exists():
            text += path.read_text() + "\n"
    return text


def check_brief(source: Path, rubric: dict) -> list[CheckResult]:
    """Check that a brief synthesized from the source would be complete.

    Accepts a directory (repo fixture) or a file (text fixture). Rather
    than running the actual skill (expensive), we verify that the source
    contains all the elements the rubric says a correct brief should have.
    """
    checks: list[CheckResult] = []
    expected = rubric.get("brief", {})

    instruction_text = _collect_instruction_text(source)
    label = "instructions" if source.is_dir() else "text"

    # Check: all expected requirements are extractable from instructions
    expected_requirements = expected.get("requirements", [])
    for req in expected_requirements:
        found = req.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: requirement '{req}' is in {label}",
            found,
            None if found else f"Requirement '{req}' not found in {label}",
        ))

    # Check: expected acceptance criteria terms are present
    expected_criteria = expected.get("acceptance_criteria_terms", [])
    for term in expected_criteria:
        found = term.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: acceptance term '{term}' is in {label}",
            found,
            None if found else f"Term '{term}' not found — brief may miss this criterion",
        ))

    # Check: time constraint is detectable (if expected)
    expected_time_limit = expected.get("time_limit")
    if expected_time_limit:
        found = expected_time_limit.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: time limit '{expected_time_limit}' is detectable",
            found,
            None if found else f"Time limit '{expected_time_limit}' not found in {label}",
        ))

    # Check: submission format is detectable (if expected)
    expected_submission = expected.get("submission_format")
    if expected_submission:
        found = expected_submission.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: submission format '{expected_submission}' is detectable",
            found,
            None if found else f"Submission format '{expected_submission}' not found",
        ))

    # Check: expected endpoint count matches
    expected_endpoint_count = expected.get("endpoint_count")
    if expected_endpoint_count is not None:
        endpoints = re.findall(
            r"`((?:GET|POST|PUT|DELETE|PATCH)\s+\S+)`", instruction_text
        )
        checks.append(CheckResult(
            f"brief: found {len(endpoints)}/{expected_endpoint_count} endpoints",
            len(endpoints) >= expected_endpoint_count,
            None if len(endpoints) >= expected_endpoint_count
            else f"Found {len(endpoints)} endpoints, expected {expected_endpoint_count}",
        ))

    return checks
