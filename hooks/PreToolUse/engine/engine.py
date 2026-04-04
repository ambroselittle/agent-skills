"""Rule evaluation engine.

Evaluates all hook rules against a tool call payload.
Priority: deny > ask > allow > proceed (no match).
"""
import re


def evaluate(payload: dict, rules: list, repo_root: str | None = None) -> dict:
    """
    Evaluate all rules against the tool call payload.

    Returns a decision dict:
      {"decision": "deny",  "reason": "..."}
      {"decision": "ask",   "reason": "..."}
      {"decision": "allow"}
      {"decision": "proceed"}   -- no rule matched, defer to Claude
    """
    from operations.filesystem import matches_read_path, matches_write_path, matches_delete_path
    from operations.git import matches_git_force_push, matches_git_reset_hard, matches_git_push_direct
    from operations.gh import matches_gh_pr_merge, matches_gh_api

    cwd = payload.get("cwd", "")

    decisions: list[tuple[str, str]] = []

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
            decisions.append((action, reason))

    # Priority: deny > ask > allow
    for action, reason in decisions:
        if action == "deny":
            return {"decision": "deny", "reason": reason}
    for action, reason in decisions:
        if action == "ask":
            return {"decision": "ask", "reason": reason}
    for action, reason in decisions:
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
