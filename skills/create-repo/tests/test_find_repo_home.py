"""Tests for the find_repo_home module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from scripts.find_repo_home import (
    discover,
    most_common_parent,
    read_cache,
    update_last_picked,
    write_cache,
)


def test_read_cache_missing(tmp_path: Path):
    with patch("scripts.find_repo_home.CACHE_PATH", tmp_path / "nope.json"):
        assert read_cache() is None


def test_read_cache_corrupt(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("not json{{{")
    with patch("scripts.find_repo_home.CACHE_PATH", cache_file):
        assert read_cache() is None


def test_write_and_read_cache(tmp_path: Path):
    cache_file = tmp_path / "sub" / "cache.json"
    with patch("scripts.find_repo_home.CACHE_PATH", cache_file):
        data = {"last_picked": "/foo", "discovered": "/bar"}
        write_cache(data)
        assert cache_file.exists()
        result = read_cache()
        assert result == data


def test_update_last_picked(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({"last_picked": None, "discovered": "/repos"}))
    with patch("scripts.find_repo_home.CACHE_PATH", cache_file):
        update_last_picked("/new/path")
        result = read_cache()
        assert result["last_picked"] == "/new/path"
        assert result["discovered"] == "/repos"


def test_update_last_picked_no_existing_cache(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    with patch("scripts.find_repo_home.CACHE_PATH", cache_file):
        update_last_picked("/some/path")
        result = read_cache()
        assert result["last_picked"] == "/some/path"


def test_most_common_parent_finds_cluster():
    git_dirs = [
        "/Users/me/Code/project-a/.git",
        "/Users/me/Code/project-b/.git",
        "/Users/me/Code/project-c/.git",
    ]
    assert most_common_parent(git_dirs, min_count=3) == "/Users/me/Code"


def test_most_common_parent_below_threshold():
    git_dirs = [
        "/Users/me/Code/project-a/.git",
        "/Users/me/Other/project-b/.git",
    ]
    assert most_common_parent(git_dirs, min_count=3) is None


def test_most_common_parent_empty():
    assert most_common_parent([]) is None


def test_most_common_parent_picks_largest_cluster():
    git_dirs = [
        "/Users/me/Code/a/.git",
        "/Users/me/Code/b/.git",
        "/Users/me/Code/c/.git",
        "/Users/me/Other/d/.git",
    ]
    assert most_common_parent(git_dirs, min_count=3) == "/Users/me/Code"


def test_discover_saves_cache(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    with (
        patch("scripts.find_repo_home.CACHE_PATH", cache_file),
        patch("scripts.find_repo_home.find_git_dirs", return_value=[]),
    ):
        result = discover()
        assert cache_file.exists()
        assert result["last_picked"] is None
        cached = json.loads(cache_file.read_text())
        assert cached == result
