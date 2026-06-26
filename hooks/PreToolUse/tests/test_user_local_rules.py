"""Tests for the personal machine-local rule overlay (load_user_local_rules)."""

import json

from engine import evaluate, load_user_local_rules

_SAMPLE_RULE = {
    "id": "user-block-example",
    "description": "Block an example command",
    "pattern": "do-not-run-me",
    "action": "deny",
    "reason": "blocked by personal overlay",
}


def _write_overlay(path, rules):
    path.write_text(json.dumps({"hooks": {"PreToolUse": {"rules": rules}}}))


def _bash(command, cwd="/repo"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def test_loads_rules_from_file(tmp_path):
    """Rules nested under hooks.PreToolUse.rules are returned."""
    overlay = tmp_path / "local-rules.json"
    _write_overlay(overlay, [_SAMPLE_RULE])
    assert load_user_local_rules(str(overlay)) == [_SAMPLE_RULE]


def test_missing_file_returns_empty(tmp_path):
    """An absent overlay file yields no rules (fail open)."""
    assert load_user_local_rules(str(tmp_path / "nope.json")) == []


def test_malformed_json_returns_empty(tmp_path):
    """Malformed JSON yields no rules rather than raising (fail open)."""
    overlay = tmp_path / "local-rules.json"
    overlay.write_text("{ not valid json")
    assert load_user_local_rules(str(overlay)) == []


def test_missing_nested_keys_returns_empty(tmp_path):
    """A file without the hooks.PreToolUse.rules path yields no rules."""
    overlay = tmp_path / "local-rules.json"
    overlay.write_text(json.dumps({"hooks": {}}))
    assert load_user_local_rules(str(overlay)) == []


def test_non_list_rules_returns_empty(tmp_path):
    """A non-list rules value is ignored."""
    overlay = tmp_path / "local-rules.json"
    overlay.write_text(json.dumps({"hooks": {"PreToolUse": {"rules": "oops"}}}))
    assert load_user_local_rules(str(overlay)) == []


def test_overlay_rule_denies_via_evaluate(tmp_path):
    """An overlay deny rule, merged into the rule set, blocks a matching command."""
    overlay = tmp_path / "local-rules.json"
    _write_overlay(overlay, [_SAMPLE_RULE])
    rules = load_user_local_rules(str(overlay))
    result = evaluate(_bash("do-not-run-me --now"), rules)
    assert result["decision"] == "deny"
    assert result["reason"] == "blocked by personal overlay"
