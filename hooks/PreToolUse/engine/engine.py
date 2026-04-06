"""Rule evaluation engine.

Evaluates all hook rules against a tool call payload.
Priority: deny > ask > allow > proceed (no match).
"""
import json
import os
import re

_repo_config_cache: dict[str, dict | None] = {}


def _load_repo_config(repo_root: str | None) -> dict | None:
    """Load .agent-skills/config.json from repo root, with caching."""
    if repo_root is None:
        return None
    if repo_root in _repo_config_cache:
        return _repo_config_cache[repo_root]

    config_path = os.path.join(repo_root, ".agent-skills", "config.json")
    config = None
    try:
        with open(config_path) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    _repo_config_cache[repo_root] = config
    return config


def _get_rule_overrides(config: dict | None, rule_id: str | None) -> dict | None:
    """Get per-repo overrides for a specific rule by id."""
    if config is None or rule_id is None:
        return None
    rules = (
        config.get("hooks", {})
        .get("PreToolUse", {})
        .get("rules", [])
    )
    for rule_override in rules:
        if rule_override.get("rule") == rule_id:
            return rule_override
    return None


def _path_matches_allowed(payload: dict, allowed_paths: list[str], repo_root: str, cwd: str) -> bool:
    """Check if all file paths in the tool call match at least one allowed pattern."""
    from resolver import matches_path_pattern
    from operations.filesystem import _path_args, _split_subcommands, _READ_COMMANDS, _WRITE_COMMANDS, _DELETE_COMMANDS, _python_open_paths

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    # Collect all file paths from the payload
    paths: list[str] = []

    if tool_name in ("Read", "Edit", "Write"):
        fp = tool_input.get("file_path", "")
        if fp:
            paths.append(fp)
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        for tokens in _split_subcommands(command):
            if not tokens:
                continue
            from pathlib import Path as P
            cmd = P(tokens[0]).name
            if cmd in _READ_COMMANDS | _WRITE_COMMANDS | _DELETE_COMMANDS:
                paths.extend(_path_args(tokens))
        paths.extend(_python_open_paths(command))

    if not paths:
        return False

    # ALL paths must match at least one allowed pattern
    for p in paths:
        matched = False
        for pattern in allowed_paths:
            if matches_path_pattern(p, pattern, repo_root, cwd):
                matched = True
                break
        if not matched:
            return False
    return True


def evaluate(payload: dict, rules: list, repo_root: str | None = None) -> dict:
    """
    Evaluate all rules against the tool call payload.

    Returns a decision dict:
      {"decision": "deny",  "reason": "..."}
      {"decision": "ask",   "reason": "..."}
      {"decision": "allow"}
      {"decision": "proceed"}   -- no rule matched, defer to Claude
    """
    from operations.filesystem import matches_read_path, matches_write_path, matches_write_content, matches_delete_path
    from operations.git import matches_git_force_push, matches_git_reset_hard, matches_git_push_direct
    from operations.gh import matches_gh_pr_merge, matches_gh_api

    cwd = payload.get("cwd", "")

    decisions: list[tuple[str, str, dict]] = []

    for rule in rules:
        operation = rule.get("operation")
        pattern = rule.get("pattern")
        action = rule["action"]
        reason = rule.get("reason", "")

        matched = False

        if operation == "read-path":
            matched = matches_read_path(payload, rule, repo_root, cwd)
        elif operation == "write-path":
            matched = matches_write_path(payload, rule, repo_root, cwd)
        elif operation == "write-content":
            matched = matches_write_content(payload, rule, repo_root, cwd)
        elif operation == "delete-path":
            matched = matches_delete_path(payload, rule, repo_root, cwd)
        elif operation == "git-force-push":
            matched = matches_git_force_push(payload, rule)
        elif operation == "git-reset-hard":
            matched = matches_git_reset_hard(payload, rule)
        elif operation == "git-push-direct":
            matched = matches_git_push_direct(payload, rule)
        elif operation == "gh-pr-merge":
            matched = matches_gh_pr_merge(payload, rule)
        elif operation == "gh-api":
            matched = matches_gh_api(payload, rule)
        elif operation == "bash-safe":
            from operations.bash import matches_bash_safe
            matched = matches_bash_safe(payload, rule)
        elif operation == "tool-name":
            matched = payload.get("tool_name", "") in rule.get("names", [])
        elif operation == "mcp-any":
            matched = payload.get("tool_name", "").startswith("mcp__")
        elif pattern is not None:
            matched = _match_pattern(payload, pattern)

        if matched:
            decisions.append((action, reason, rule))

    # Load per-repo config for override checking
    repo_config = _load_repo_config(repo_root)

    # Priority: deny > ask > allow
    for action, reason, rule_ref in decisions:
        if action == "deny":
            # Check for per-repo override
            rule_id = rule_ref.get("id") if rule_ref else None
            overrides = _get_rule_overrides(repo_config, rule_id)
            if overrides and "allowedPaths" in overrides:
                if _path_matches_allowed(payload, overrides["allowedPaths"], repo_root or "", cwd):
                    continue  # Skip this deny — path is allowed by repo config
            return {"decision": "deny", "reason": reason}
    for action, reason, rule_ref in decisions:
        if action == "ask":
            return {"decision": "ask", "reason": reason}
    for action, reason, rule_ref in decisions:
        if action == "allow":
            return {"decision": "allow"}

    return {"decision": "proceed"}


def _strip_heredocs(command: str) -> str:
    """Remove heredoc bodies from a shell command before pattern matching."""
    return re.sub(
        r"<<-?\s*['\"]?(\w+)['\"]?\n(?:.*\n)*?\1[ \t]*(?:\n|$)",
        "",
        command,
    )


def _match_pattern(payload: dict, pattern: str) -> bool:
    """Match a raw pattern rule against the tool call."""
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "Bash":
        command = _strip_heredocs(tool_input.get("command", ""))
        return bool(re.search(pattern, command))
    elif tool_name in ("Read", "Edit", "Write"):
        path = tool_input.get("file_path", "")
        return bool(re.search(pattern, path))

    return False
