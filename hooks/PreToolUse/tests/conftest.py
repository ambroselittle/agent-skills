"""Pytest configuration: add engine/ to sys.path so tests can import engine, resolver, etc."""
import json
import sys
from pathlib import Path

import pytest

_HOOK_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_HOOK_ROOT / "engine"))

RULES_JSON = _HOOK_ROOT / "rules.json"


@pytest.fixture
def rule(request):
    data = json.loads(RULES_JSON.read_text())
    all_rules = {r["description"]: r for r in data.get("hook-rules", [])}
    description = getattr(request.module, "RULE_DESCRIPTION", None)
    if description is None:
        pytest.skip("No RULE_DESCRIPTION defined")
    if description not in all_rules:
        raise ValueError(f"Rule not found in rules.json: {description!r}")
    return all_rules[description]
