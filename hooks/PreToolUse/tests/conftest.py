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
    rules_list = data.get("hook-rules", [])

    # Prefer RULE_ID, fall back to RULE_DESCRIPTION for backwards compat
    rule_id = getattr(request.module, "RULE_ID", None)
    description = getattr(request.module, "RULE_DESCRIPTION", None)

    if rule_id:
        by_id = {r["id"]: r for r in rules_list if "id" in r}
        if rule_id not in by_id:
            raise ValueError(f"Rule not found by id in rules.json: {rule_id!r}")
        return by_id[rule_id]

    if description:
        by_desc = {r["description"]: r for r in rules_list}
        if description not in by_desc:
            raise ValueError(f"Rule not found by description in rules.json: {description!r}")
        return by_desc[description]

    pytest.skip("No RULE_ID or RULE_DESCRIPTION defined")
