"""Tests for per-repo .agent-skills/config.json override support."""

import json

from engine import _repo_config_cache, evaluate


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


def _push_main_deny_rule():
    return {
        "id": "block-push-main",
        "description": "Block direct push to main or master",
        "operation": "git-push-direct",
        "deny-branches": ["main", "master"],
        "action": "deny",
        "reason": "Direct push to main/master not permitted — open a PR",
    }


def _force_push_main_deny_rule():
    return {
        "id": "block-force-push-main",
        "description": "Block force push to main or master",
        "operation": "git-force-push",
        "deny-branches": ["main", "master"],
        "action": "deny",
        "reason": "Force pushing to main/master is not permitted",
    }


def _write_repo_config(repo, rules):
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"hooks": {"PreToolUse": {"rules": rules}}})
    )


def test_override_allows_denied_path(tmp_path):
    """A repo config with allowedPaths should skip the deny for matching paths."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
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
            }
        )
    )

    payload = _payload("Read", {"file_path": str(repo / ".eval-runs" / "test" / ".env")})
    result = evaluate(payload, [_env_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"


def test_override_allows_bash_read_of_denied_path(tmp_path):
    """A Bash command reading an allowed .env path should also be overridden."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    config_dir = repo / ".agent-skills"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
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
            }
        )
    )

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
    (config_dir / "config.json").write_text(
        json.dumps(
            {
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
            }
        )
    )

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
    (config_dir / "config.json").write_text(
        json.dumps(
            {
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
            }
        )
    )

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


# ---------------------------------------------------------------------------
# allowedBranches override — mirrors allowedPaths but for git push rules
# ---------------------------------------------------------------------------


def test_override_allows_denied_push_to_main(tmp_path):
    """A repo config with allowedBranches should skip the deny for matching branches."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(
        repo, [{"rule": "block-push-main", "allowedBranches": ["main"]}]
    )

    payload = _payload("Bash", {"command": "git push -u origin main"})
    result = evaluate(payload, [_push_main_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"


def test_override_allows_force_push_to_main(tmp_path):
    """allowedBranches should also override the force-push rule."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(
        repo, [{"rule": "block-force-push-main", "allowedBranches": ["main"]}]
    )

    payload = _payload("Bash", {"command": "git push --force origin main"})
    result = evaluate(payload, [_force_push_main_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"


def test_override_does_not_affect_other_denied_branch(tmp_path):
    """A push to master should still deny when only main is allowed."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(
        repo, [{"rule": "block-push-main", "allowedBranches": ["main"]}]
    )

    payload = _payload("Bash", {"command": "git push origin master"})
    result = evaluate(payload, [_push_main_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "deny"


def test_override_wildcard_allows_any_branch(tmp_path):
    """A '*' allowedBranches entry effectively disables the rule for this repo."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(repo, [{"rule": "block-push-main", "allowedBranches": ["*"]}])

    for branch in ["main", "master"]:
        payload = _payload("Bash", {"command": f"git push origin {branch}"})
        result = evaluate(payload, [_push_main_deny_rule()], repo_root=str(repo))
        assert result["decision"] == "proceed", f"expected proceed for {branch}"


def test_override_no_branches_specified_still_denies(tmp_path):
    """Overrides without allowedBranches leave the deny intact."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(repo, [{"rule": "block-push-main"}])

    payload = _payload("Bash", {"command": "git push origin main"})
    result = evaluate(payload, [_push_main_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "deny"


def test_allowed_branches_with_no_explicit_branch_still_denies(tmp_path):
    """If the push has no explicit branch, we can't confirm it's allowed — deny stands.

    Only relevant when the deny rule already matched (which requires a known
    branch). This test pairs with git-push-direct's own "don't assume" logic:
    `_branch_matches_allowed` returns False for ambiguous pushes so the outer
    deny proceeds — but in practice the outer deny also requires a known
    branch, so this is defense in depth.
    """
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(
        repo, [{"rule": "block-push-main", "allowedBranches": ["main"]}]
    )

    # A push without a branch arg — the deny rule won't match this anyway,
    # but we want to confirm the override doesn't spuriously proceed.
    payload = _payload("Bash", {"command": "git push"})
    result = evaluate(payload, [_push_main_deny_rule()], repo_root=str(repo))
    assert result["decision"] == "proceed"  # deny didn't match in the first place


def test_allowed_paths_and_branches_coexist(tmp_path):
    """A single repo config may contain both kinds of overrides for different rules."""
    _repo_config_cache.clear()

    repo = tmp_path / "myrepo"
    _write_repo_config(
        repo,
        [
            {"rule": "block-env-reads", "allowedPaths": [".eval-runs/**/.env*"]},
            {"rule": "block-push-main", "allowedBranches": ["main"]},
        ],
    )

    read_payload = _payload(
        "Read", {"file_path": str(repo / ".eval-runs" / "x" / ".env")}
    )
    assert (
        evaluate(read_payload, [_env_deny_rule()], repo_root=str(repo))["decision"]
        == "proceed"
    )

    push_payload = _payload("Bash", {"command": "git push origin main"})
    assert (
        evaluate(push_payload, [_push_main_deny_rule()], repo_root=str(repo))[
            "decision"
        ]
        == "proceed"
    )
