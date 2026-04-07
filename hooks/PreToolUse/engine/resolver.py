"""Path normalization, repo-root detection, and glob matching for the hook rules engine."""

import os
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path


def resolve_repo_root(cwd: str) -> str | None:
    """Detect the git repo root from cwd."""
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def normalize_path(path: str, cwd: str | None = None) -> str:
    """Expand ~ and return as an absolute path. Does not follow symlinks."""
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        return expanded
    if cwd:
        return os.path.normpath(os.path.join(cwd, expanded))
    return os.path.abspath(expanded)


def matches_path_pattern(file_path: str, pattern: str, repo_root: str | None, cwd: str) -> bool:
    """
    Match a file path against a rule pattern.

    Anchored patterns (~/... or /...):
      Resolved absolutely -- matched against the full filesystem path.

    Unanchored patterns (**/.env, *.key):
      Resolved relative to repo_root (or cwd if not in a repo).
    """
    resolved = normalize_path(file_path, cwd)

    if pattern.startswith("~"):
        expanded = str(Path(pattern).expanduser())
        return _glob_match(resolved, expanded)

    if pattern.startswith("/"):
        return _glob_match(resolved, pattern)

    base = repo_root or cwd
    if not base:
        return False
    full_pattern = str(Path(base) / pattern)
    return _glob_match(resolved, full_pattern)


def _glob_match(path: str, pattern: str) -> bool:
    """Match a path against a glob pattern. Supports *, ?, **."""
    if "**" not in pattern:
        from pathlib import PurePosixPath

        try:
            return PurePosixPath(path).match(pattern)
        except (ValueError, TypeError):
            return False
    return _double_star_match(path, pattern)


def _double_star_match(path: str, pattern: str) -> bool:
    """Implement ** glob matching."""
    parts = re.split(r"\*\*/?", pattern)

    if len(parts) == 1:
        return fnmatch(path, pattern)

    regex_parts = [_glob_segment_to_regex(p) for p in parts]

    result = regex_parts[0]
    for i in range(1, len(regex_parts)):
        if regex_parts[i] == "" and i == len(regex_parts) - 1:
            result += ".*"
        else:
            result += "(?:.+/)?" + regex_parts[i]
    return bool(re.fullmatch(result, path))


def _glob_segment_to_regex(segment: str) -> str:
    """Convert a glob segment (no **) to a regex string."""
    result = ""
    for char in segment:
        if char == "*":
            result += "[^/]*"
        elif char == "?":
            result += "[^/]"
        elif char in r"\.+^${}()|[]":
            result += re.escape(char)
        else:
            result += char
    return result
