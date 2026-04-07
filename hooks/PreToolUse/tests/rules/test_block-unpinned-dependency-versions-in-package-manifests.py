"""Tests for rule: Block unpinned dependency versions in package manifests."""

from engine import evaluate

REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block unpinned dependency versions in package manifests"
RULE_ID = "block-unpinned-deps"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


# --- test_match: should deny ---


def test_match(rule):
    """Write to package.json with 'latest' is denied."""
    content = '{\n  "dependencies": {\n    "express": "latest"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_match_star(rule):
    """Write to package.json with '*' is denied."""
    content = '{\n  "devDependencies": {\n    "prettier": "*"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_match_nested_package_json(rule):
    """Write to nested package.json with 'latest' is denied."""
    content = '{\n  "dependencies": {\n    "react": "latest"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/apps/web/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_match_edit_new_string(rule):
    """Edit adding 'latest' to package.json is denied."""
    payload = _payload(
        "Edit",
        {
            "file_path": f"{REPO}/package.json",
            "new_string": '    "jsdom": "latest"\n',
        },
    )
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


# --- test_no_match: should proceed ---


def test_no_match(rule):
    """Write to package.json with pinned versions is fine."""
    content = '{\n  "dependencies": {\n    "express": "^4.18.2"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_no_match_non_manifest(rule):
    """Write to a non-manifest file with 'latest' is fine."""
    content = 'const version = "latest"'
    payload = _payload("Write", {"file_path": f"{REPO}/src/config.js", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_no_match_pyproject_pinned(rule):
    """Write to pyproject.toml with pinned versions is fine."""
    content = '[project]\ndependencies = [\n    "fastapi>=0.115.0",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


# --- boundary cases ---


def test_boundary_workspace_star_allowed(rule):
    """workspace:* is NOT unpinned — it's a pnpm workspace protocol reference."""
    content = '{\n  "dependencies": {\n    "@myapp/db": "workspace:*"\n  }\n}'
    payload = _payload("Write", {"file_path": f"{REPO}/package.json", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_pyproject_not_matched(rule):
    """This rule only applies to package.json, not pyproject.toml."""
    content = '[project]\ndependencies = [\n    "requests": "latest",\n]'
    payload = _payload("Write", {"file_path": f"{REPO}/pyproject.toml", "content": content})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_read_not_matched(rule):
    """Read tool is not matched by write-content operation."""
    payload = _payload("Read", {"file_path": f"{REPO}/package.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_bash_not_matched(rule):
    """Bash tool is not matched by write-content operation."""
    payload = _payload("Bash", {"command": "echo latest > package.json"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
