"""Filesystem operation handlers: read-path, write-path, delete-path."""
import re
from pathlib import Path

from operations.common import _tokenize, _split_subcommands, _COMPOUND_OPS
from resolver import matches_path_pattern, normalize_path

_READ_COMMANDS = frozenset([
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep",
    "rg", "ripgrep", "awk", "sed", "sort", "wc", "diff", "cut", "strings",
])

_WRITE_COMMANDS = frozenset([
    "cp", "mv", "tee", "install",
])

_DELETE_COMMANDS = frozenset([
    "rm", "rmdir", "unlink",
])

_REDIRECT_WRITE_RE = re.compile(r'(?:>>?)\s*([^\s;|&]+)')


def _path_args(tokens: list[str]) -> list[str]:
    paths = []
    skip_next = False
    for tok in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if tok in ("-e", "-f", "--file", "--include", "--exclude", "-m", "-A", "-B", "-C"):
            skip_next = True
            continue
        if tok.startswith("-"):
            continue
        if tok.startswith(("/", "~", "./", "../")) or "." in tok or "/" in tok:
            paths.append(tok)
    return paths


def _redirect_targets(command: str) -> list[str]:
    return _REDIRECT_WRITE_RE.findall(command)


def _python_open_paths(command: str) -> list[str]:
    return re.findall(r"""open\s*\(\s*['"]([^'"]+)['"]""", command)


def _any_path_matches(paths: list[str], rule_paths: list[str], repo_root: str | None, cwd: str) -> bool:
    for p in paths:
        for pattern in rule_paths:
            if matches_path_pattern(p, pattern, repo_root, cwd):
                return True
    return False


def matches_read_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])

    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return _any_path_matches([fp], rule_paths, repo_root, cwd)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates: list[str] = []

        for tokens in _split_subcommands(command):
            if not tokens:
                continue
            cmd = Path(tokens[0]).name
            if cmd in _READ_COMMANDS:
                candidates.extend(_path_args(tokens))

        candidates.extend(_python_open_paths(command))

        for m in re.finditer(r'<\s*([^\s;|&<>]+)', command):
            candidates.append(m.group(1))

        return _any_path_matches(candidates, rule_paths, repo_root, cwd)

    return False


def matches_write_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])

    if tool_name == "Edit":
        fp = tool_input.get("file_path", "")
        return _any_path_matches([fp], rule_paths, repo_root, cwd)

    if tool_name == "Write":
        fp = tool_input.get("file_path", "")
        return _any_path_matches([fp], rule_paths, repo_root, cwd)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates: list[str] = []

        for tokens in _split_subcommands(command):
            if not tokens:
                continue
            cmd = Path(tokens[0]).name

            if cmd in _WRITE_COMMANDS:
                args = _path_args(tokens)
                if args:
                    candidates.extend(args)

            if cmd == "tee":
                candidates.extend(_path_args(tokens))

        candidates.extend(_redirect_targets(command))

        return _any_path_matches(candidates, rule_paths, repo_root, cwd)

    return False


def matches_write_content(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    """Match writes to specific file paths whose content matches forbidden patterns.

    Rule format:
        {
            "operation": "write-content",
            "paths": ["**/package.json", "**/pyproject.toml"],
            "content_patterns": ["\"latest\"", "\"\\*\""],
            "action": "deny",
            "reason": "..."
        }

    Matches when BOTH the file path matches AND any content pattern is found.
    Checks Write (full content) and Edit (new_string only) tool calls.
    """
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])
    content_patterns = rule.get("content_patterns", [])

    if tool_name == "Write":
        fp = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        fp = tool_input.get("file_path", "")
        content = tool_input.get("new_string", "")
    else:
        return False

    if not _any_path_matches([fp], rule_paths, repo_root, cwd):
        return False

    for pattern in content_patterns:
        if re.search(pattern, content):
            return True

    return False


def matches_delete_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])

    if tool_name != "Bash":
        return False

    command = tool_input.get("command", "")
    candidates: list[str] = []

    for tokens in _split_subcommands(command):
        if not tokens:
            continue
        cmd = Path(tokens[0]).name
        if cmd in _DELETE_COMMANDS:
            candidates.extend(_path_args(tokens))

    return _any_path_matches(candidates, rule_paths, repo_root, cwd)
