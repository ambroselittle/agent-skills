"""Meta-test: every rule in hook-rules must have a test file with required functions.

For each rule in hook-rules:
  1. Derive the test file path from the rule's description slug
  2. Assert the test file exists
  3. Import it and assert test_match, test_no_match, and at least one test_boundary* function exist

Run with: pytest hooks/PreToolUse/tests/test_verify_rule_conventions.py
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

# Path to rules.json (source of truth)
RULES_JSON = Path(__file__).parents[1] / "rules.json"
RULES_DIR = Path(__file__).parent / "rules"


def description_to_slug(description: str) -> str:
    """
    Convert a rule description to a filesystem-safe slug for the test file name.

    Truncates at the first em-dash or opening paren (these mark clarifications,
    not the rule name). Then lowercases and replaces non-alphanumeric runs with hyphens.

    Examples:
      "Block reading SSH keys"               -> "block-reading-ssh-keys"
      "Block reading .env files -- apply..."  -> "block-reading-env-files"
      "Allow force push to feature branches (e.g. after rebase)" -> "allow-force-push-to-feature-branches"
    """
    short = re.split(r"[—(]", description)[0].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", short.lower())
    slug = slug.strip("-")
    if len(slug) > 70:
        slug = slug[:70].rstrip("-")
    return slug


def load_hook_rules() -> list[dict]:
    with open(RULES_JSON) as f:
        data = json.load(f)
    return data.get("hook-rules", [])


def load_module_from_path(path: Path):
    """Import a Python file as a module."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Generate one test per rule
# ---------------------------------------------------------------------------

_rules = load_hook_rules()
_rule_params = [
    pytest.param(rule, id=description_to_slug(rule["description"]))
    for rule in _rules
]


@pytest.mark.parametrize("rule", _rule_params)
def test_rule_has_test_file(rule: dict) -> None:
    """Every hook rule must have a corresponding test file in tests/rules/."""
    slug = description_to_slug(rule["description"])
    test_file = RULES_DIR / f"test_{slug}.py"
    assert test_file.exists(), (
        f"Missing test file for rule '{rule['description']}'\n"
        f"Expected: {test_file}\n"
        f"Create it with test_match, test_no_match, and test_boundary* functions."
    )


@pytest.mark.parametrize("rule", _rule_params)
def test_rule_has_required_functions(rule: dict) -> None:
    """Every rule's test file must define test_match, test_no_match, and test_boundary*."""
    slug = description_to_slug(rule["description"])
    test_file = RULES_DIR / f"test_{slug}.py"

    if not test_file.exists():
        pytest.skip(f"Test file not found (covered by test_rule_has_test_file): {test_file}")

    # Add the tests/rules dir to sys.path temporarily so the module can import conftest setup
    sys.path.insert(0, str(RULES_DIR.parent))
    try:
        module = load_module_from_path(test_file)
    finally:
        sys.path.pop(0)

    functions = [name for name in dir(module) if callable(getattr(module, name))]

    assert "test_match" in functions, (
        f"test file for '{rule['description']}' is missing test_match"
    )
    assert "test_no_match" in functions, (
        f"test file for '{rule['description']}' is missing test_no_match"
    )
    boundary_fns = [f for f in functions if f.startswith("test_boundary")]
    assert boundary_fns, (
        f"test file for '{rule['description']}' is missing at least one test_boundary* function"
    )
