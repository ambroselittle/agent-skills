"""Tests for rule: Block unbounded dependency ranges in pyproject.toml."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block unbounded dependency ranges in pyproject.toml"
RULE_ID = "block-unbounded-python-deps"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


# --- test_match: should deny ---


def test_match(rule):
    """Bare >= in pyproject.toml is denied."""
    content = '[project]\ndependencies = [\n    "fastapi>=0.115.0",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_match_nested(rule):
    """Bare >= in nested pyproject.toml is denied."""
    content = '[project]\ndependencies = [\n    "sqlmodel>=0.0.22",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/apps/api/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_match_edit(rule):
    """Edit adding bare >= to pyproject.toml is denied."""
    payload = _payload("Edit", {
        "file_path": f"{REPO}/pyproject.toml",
        "new_string": '    "requests>=2.31.0",\n',
    })
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


# --- test_no_match: should proceed ---


def test_no_match(rule):
    """Compatible release ~= is fine."""
    content = '[project]\ndependencies = [\n    "fastapi~=0.115.0",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_no_match_bounded_range(rule):
    """Bounded >= with < is fine."""
    content = '[project]\ndependencies = [\n    "fastapi>=0.115.0,<1",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_no_match_exact(rule):
    """Exact version is fine."""
    content = '[project]\ndependencies = [\n    "fastapi==0.115.0",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_no_match_package_json(rule):
    """This rule only applies to pyproject.toml, not package.json."""
    content = '{\n  "dependencies": {\n    "express": ">=4.18.0"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


# --- boundary cases ---


def test_boundary_requires_python_allowed(rule):
    """requires-python = '>=3.12' is NOT a dep — should not match."""
    content = '[project]\nrequires-python = ">=3.12"\n'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_hatchling_build_requires(rule):
    """Build system requires with exact version is fine."""
    content = '[build-system]\nrequires = ["hatchling"]\n'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_multiple_deps_one_bad(rule):
    """If any dep is unbounded, deny."""
    content = '[project]\ndependencies = [\n    "fastapi~=0.115.0",\n    "requests>=2.31.0",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"
