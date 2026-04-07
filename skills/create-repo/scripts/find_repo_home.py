"""Discover where the user keeps their repos.

Checks a cache file first, falls back to scanning the filesystem.
Outputs JSON with discovered paths for the location picker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

CACHE_PATH = Path.home() / ".agent-skills" / ".repo-home-cache.json"


def read_cache() -> dict | None:
    """Read and return cache if it exists."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def write_cache(data: dict) -> None:
    """Write cache file, creating directory if needed."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2) + "\n")


def find_git_dirs(root: str, max_depth: int, limit: int) -> list[str]:
    """Find .git directories under root, bounded by depth and count."""
    try:
        proc = subprocess.run(
            ["find", root, "-maxdepth", str(max_depth), "-name", ".git", "-type", "d"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = [line for line in proc.stdout.strip().splitlines() if line]
        return lines[:limit]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def most_common_parent(git_dirs: list[str], min_count: int = 3) -> str | None:
    """Find the most common grandparent directory of .git dirs.

    Each .git dir is at <parent>/<repo>/.git, so the grandparent is <parent>.
    Returns the path if it contains at least min_count repos.
    """
    parents = []
    for git_dir in git_dirs:
        # .git -> repo dir -> parent of repo
        repo_dir = os.path.dirname(git_dir)
        parent = os.path.dirname(repo_dir)
        if parent:
            parents.append(parent)

    if not parents:
        return None

    counter = Counter(parents)
    top_path, top_count = counter.most_common(1)[0]
    if top_count >= min_count:
        return top_path
    return None


def discover() -> dict:
    """Run full discovery and return results."""
    result: dict = {"last_picked": None, "discovered": None, "discovered_at": None}

    # Check CWD for repos
    cwd = os.getcwd()
    cwd_git_dirs = find_git_dirs(cwd, max_depth=2, limit=5)
    if cwd_git_dirs:
        result["cwd_match"] = cwd

    # Broader search under ~
    home_git_dirs = find_git_dirs(str(Path.home()), max_depth=3, limit=20)
    discovered = most_common_parent(home_git_dirs)
    if discovered:
        result["discovered"] = discovered
        result["discovered_at"] = datetime.now(UTC).isoformat()

    # Save to cache
    write_cache(result)

    return result


def update_last_picked(path: str) -> None:
    """Update the last_picked field in the cache."""
    cache = read_cache() or {}
    cache["last_picked"] = path
    write_cache(cache)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Find where repos live")
    parser.add_argument(
        "--update-last-picked",
        metavar="PATH",
        help="Update last_picked in cache and exit",
    )
    args = parser.parse_args()

    if args.update_last_picked:
        update_last_picked(args.update_last_picked)
        return

    # Check cache first
    cache = read_cache()
    if cache:
        json.dump(cache, sys.stdout, indent=2)
        print()
        return

    # No cache — run discovery
    result = discover()
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
