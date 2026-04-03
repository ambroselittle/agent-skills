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


def extract_requirements_from_readme(readme_path: Path) -> list[str]:
    """Extract requirement-like lines from a README.

    Looks for numbered lists, bullet points under requirement-related headers,
    and structured requirement sections.
    """
    if not readme_path.exists():
        return []

    text = readme_path.read_text()
    requirements: list[str] = []

    # Find numbered items (1. xxx, 2. xxx)
    numbered = re.findall(r"^\s*\d+\.\s+\*\*(.+?)\*\*", text, re.MULTILINE)
    requirements.extend(numbered)

    # Find backtick-wrapped items that look like endpoints or commands
    endpoints = re.findall(r"`((?:GET|POST|PUT|DELETE|PATCH)\s+\S+)`", text)
    requirements.extend(endpoints)

    return requirements


def check_brief(fixture_dir: Path, rubric: dict) -> list[CheckResult]:
    """Check that a brief synthesized from the fixture would be complete.

    Rather than running the actual skill (expensive), we verify that the
    fixture's instruction files contain all the elements the rubric says
    a correct brief should have.
    """
    checks: list[CheckResult] = []
    expected = rubric.get("brief", {})

    # Read all instruction text from the fixture
    instruction_text = ""
    readme_path = fixture_dir / "README.md"
    if readme_path.exists():
        instruction_text = readme_path.read_text()

    for alt in ["INSTRUCTIONS.md", "PROMPT.md", "CHALLENGE.md"]:
        alt_path = fixture_dir / alt
        if alt_path.exists():
            instruction_text += "\n" + alt_path.read_text()

    # Check: all expected requirements are extractable from instructions
    expected_requirements = expected.get("requirements", [])
    for req in expected_requirements:
        found = req.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: requirement '{req}' is in instructions",
            found,
            None if found else f"Requirement '{req}' not found in instruction text",
        ))

    # Check: expected acceptance criteria terms are present
    expected_criteria = expected.get("acceptance_criteria_terms", [])
    for term in expected_criteria:
        found = term.lower() in instruction_text.lower()
        checks.append(CheckResult(
            f"brief: acceptance term '{term}' is in instructions",
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
            None if found else f"Time limit '{expected_time_limit}' not found in instructions",
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
