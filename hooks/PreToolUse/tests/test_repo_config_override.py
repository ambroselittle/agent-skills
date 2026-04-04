"""Tests for per-repo .agent-skills/config.json override support."""

import json
import os
from pathlib import Path

from engine import evaluate, _repo_config_cache


def _payload(tool_name, tool_input, cwd="/repo"):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def _env_deny_rule():
    return {
        "id": "block-env-reads",
        "description": "Block reading .env files",
        "operation": "read-path",
        "paths": ["**/.env", "**/.env.*"],
        "action": "deny",
        "reason": "Env files may contain secrets",
    }


def test_override_allows_denied_path(tmp_path):
    """A repo config with allowedPaths should skip the deny for matching paths."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": {
                "rules": [
                    {
                        "rule": "block-env-reads",
                        "allowedPaths": [".eval-runs/**/.env*"],
                    }
                ]
            }
        }
    }))

    payload = _payload("Read", {"file_path": str(repo / ".eval-runs" / "test" / ".env")})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"


def test_override_allows_bash_read_of_denied_path(tmp_path):
    """A Bash command reading an allowed .env path should also be overridden."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": {
                "rules": [
                    {
                        "rule": "block-env-reads",
                        "allowedPaths": [".eval-runs/**/.env*"],
                    }
                ]
            }
        }
    }))

    env_path = str(repo / ".eval-runs" / "test" / ".env.ports")
    payload = _payload("Bash", {"command": f"wc -l {env_path}"})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"


def test_override_does_not_affect_non_matching_paths(tmp_path):
    """Paths not matching allowedPaths should still be denied."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": {
                "rules": [
                    {
                        "rule": "block-env-reads",
                        "allowedPaths": [".eval-runs/**/.env*"],
                    }
                ]
            }
        }
    }))

    payload = _payload("Read", {"file_path": str(repo / ".env")})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "deny"


def test_no_config_file_behaves_normally(tmp_path):
    """Without a config file, deny rules work as before."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    repo.mkdir()

    payload = _payload("Read", {"file_path": str(repo / ".env")})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "deny"


def test_rule_without_id_is_not_overridable(tmp_path):
    """Rules without an id field cannot be overridden by config."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": {
                "rules": [
                    {
                        "rule": "block-env-reads",
                        "allowedPaths": ["**/.env*"],
                    }
                ]
            }
        }
    }))

    rule_no_id = {
        "description": "Block reading .env files",
        "operation": "read-path",
        "paths": ["**/.env"],
        "action": "deny",
        "reason": "blocked",
    }

    payload = _payload("Read", {"file_path": str(repo / ".env")})
    result = evaluate(payload, [rule_no_id], repo_root=str(repo))
    assert result["decision"] == "deny"


def test_malformed_config_is_ignored(tmp_path):
    """A malformed config.json should be silently ignored."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("not valid json{{{")

    payload = _payload("Read", {"file_path": str(repo / ".env")})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "deny"
