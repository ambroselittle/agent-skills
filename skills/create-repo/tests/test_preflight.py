"""Tests for the preflight environment checker."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from scripts.preflight import (
    CheckResult,
    Status,
    generate_install_script,
    parse_version,
    preflight,
    run_check,
    run_runtime_check,
    version_tuple,
)

# --- parse_version ---


@pytest.mark.parametrize(
    "text, pattern, expected",
    [
        ("git version 2.43.0", r"git version (\d+\.\d+(?:\.\d+)?)", "2.43.0"),
        ("v22.5.0", r"v(\d+\.\d+(?:\.\d+)?)", "22.5.0"),
        ("10.1.0", r"(\d+\.\d+(?:\.\d+)?)", "10.1.0"),
        ("Docker version 27.3.1, build afdd53b", r"Docker version (\d+\.\d+(?:\.\d+)?)", "27.3.1"),
        ("gh version 2.89.0 (2026-01-01)", r"gh version (\d+\.\d+(?:\.\d+)?)", "2.89.0"),
        ("uv 0.11.2", r"uv (\d+\.\d+(?:\.\d+)?)", "0.11.2"),
        ("no version here", r"v(\d+\.\d+(?:\.\d+)?)", None),
        ("", r"v(\d+\.\d+(?:\.\d+)?)", None),
    ],
)
def test_parse_version(text: str, pattern: str, expected: str | None):
    assert parse_version(text, pattern) == expected


# --- version_tuple ---


def test_version_tuple():
    assert version_tuple("22.5.0") == (22, 5, 0)
    assert version_tuple("10.1") == (10, 1)
    assert version_tuple("2.43.0") == (2, 43, 0)


# --- run_check ---


def _mock_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Create a mock subprocess.run result."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_check_ok():
    check = {
        "tool": "node",
        "command": ["node", "--version"],
        "pattern": r"v(\d+\.\d+(?:\.\d+)?)",
        "min": (22, 0),
        "install": "brew install fnm && fnm install 22",
    }
    with patch("scripts.preflight.subprocess.run", return_value=_mock_run(stdout="v22.5.0")):
        result = run_check(check)
    assert result.status == Status.OK
    assert result.found_version == "22.5.0"
    assert result.tool == "node"


def test_run_check_outdated():
    check = {
        "tool": "node",
        "command": ["node", "--version"],
        "pattern": r"v(\d+\.\d+(?:\.\d+)?)",
        "min": (22, 0),
        "install": "brew install fnm && fnm install 22",
    }
    with patch("scripts.preflight.subprocess.run", return_value=_mock_run(stdout="v20.11.0")):
        result = run_check(check)
    assert result.status == Status.OUTDATED
    assert result.found_version == "20.11.0"
    assert result.required_version == "22.0+"


def test_run_check_missing_not_installed():
    check = {
        "tool": "pnpm",
        "command": ["pnpm", "--version"],
        "pattern": r"(\d+\.\d+(?:\.\d+)?)",
        "min": (10, 0),
        "install": "brew install pnpm",
    }
    with patch("scripts.preflight.subprocess.run", side_effect=FileNotFoundError):
        result = run_check(check)
    assert result.status == Status.MISSING
    assert result.found_version is None


def test_run_check_missing_unparseable_output():
    check = {
        "tool": "git",
        "command": ["git", "--version"],
        "pattern": r"git version (\d+\.\d+(?:\.\d+)?)",
        "min": (2, 39),
        "install": "xcode-select --install",
    }
    with patch(
        "scripts.preflight.subprocess.run", return_value=_mock_run(stdout="something unexpected")
    ):
        result = run_check(check)
    assert result.status == Status.MISSING
    assert result.found_version is None


def test_run_check_timeout():
    check = {
        "tool": "docker",
        "command": ["docker", "--version"],
        "pattern": r"Docker version (\d+\.\d+(?:\.\d+)?)",
        "min": (27, 0),
        "install": "brew install --cask docker",
    }
    with patch(
        "scripts.preflight.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=10),
    ):
        result = run_check(check)
    assert result.status == Status.MISSING


def test_run_check_no_min_version():
    """Tools with min=None are OK as long as they're found."""
    check = {
        "tool": "xcodegen",
        "command": ["xcodegen", "--version"],
        "pattern": r"Version:?\s*(\d+\.\d+(?:\.\d+)?)",
        "min": None,
        "install": "brew install xcodegen",
    }
    with patch(
        "scripts.preflight.subprocess.run", return_value=_mock_run(stdout="Version: 2.42.0")
    ):
        result = run_check(check)
    assert result.status == Status.OK
    assert result.required_version is None


# --- run_runtime_check ---


def test_runtime_check_ok():
    check = {
        "tool": "gh (authenticated)",
        "command": ["gh", "auth", "status"],
        "success_means": "authenticated",
        "install": "gh auth login",
    }
    with patch("scripts.preflight.subprocess.run", return_value=_mock_run(returncode=0)):
        result = run_runtime_check(check)
    assert result.status == Status.OK
    assert result.found_version == "authenticated"


def test_runtime_check_failure():
    check = {
        "tool": "docker (daemon)",
        "command": ["docker", "info"],
        "success_means": "daemon running",
        "install": "open -a Docker",
    }
    with patch(
        "scripts.preflight.subprocess.run",
        return_value=_mock_run(returncode=1, stderr="Cannot connect"),
    ):
        result = run_runtime_check(check)
    assert result.status == Status.MISSING


def test_runtime_check_not_installed():
    check = {
        "tool": "gh (authenticated)",
        "command": ["gh", "auth", "status"],
        "success_means": "authenticated",
        "install": "gh auth login",
    }
    with patch("scripts.preflight.subprocess.run", side_effect=FileNotFoundError):
        result = run_runtime_check(check)
    assert result.status == Status.MISSING


# --- preflight (integration with mocked subprocess) ---


def _make_version_responses(responses: dict[str, str | None]):
    """Build a side_effect function that returns canned output per command."""

    def fake_run(cmd, **kwargs):
        key = cmd[0]
        if key in responses:
            val = responses[key]
            if val is None:
                raise FileNotFoundError
            return _mock_run(stdout=val)
        # Runtime checks (gh auth status, docker info)
        cmd_str = " ".join(cmd)
        if cmd_str in responses:
            val = responses[cmd_str]
            if val is None:
                return _mock_run(returncode=1)
            return _mock_run(stdout=val, returncode=0)
        return _mock_run(returncode=1)

    return fake_run


def test_preflight_fullstack_ts_all_present():
    responses = {
        "git": "git version 2.53.0",
        "gh": "gh version 2.89.0 (2026-01-01)",
        "node": "v22.22.2",
        "pnpm": "10.33.0",
        "docker": "Docker version 29.3.1, build afdd53b",
        "gh auth status": "Logged in",
        "docker info": "Server Version: 29.3.1",
    }
    with patch("scripts.preflight.subprocess.run", side_effect=_make_version_responses(responses)):
        results = preflight("fullstack-ts")

    assert all(r.status == Status.OK for r in results), [
        f"{r.tool}: {r.status}" for r in results if r.status != Status.OK
    ]


def test_preflight_template_specific_checks_python():
    """Python templates add a uv check."""
    responses = {
        "git": "git version 2.53.0",
        "gh": "gh version 2.89.0",
        "node": "v22.22.2",
        "pnpm": "10.33.0",
        "docker": "Docker version 29.3.1",
        "uv": None,  # uv not installed
        "gh auth status": "Logged in",
        "docker info": "ok",
    }
    with patch("scripts.preflight.subprocess.run", side_effect=_make_version_responses(responses)):
        results = preflight("fullstack-python")

    tool_names = [r.tool for r in results]
    assert "uv" in tool_names
    uv_result = next(r for r in results if r.tool == "uv")
    assert uv_result.status == Status.MISSING


def test_preflight_template_specific_not_included_for_other_templates():
    """fullstack-ts should NOT include uv or xcodegen checks."""
    responses = {
        "git": "git version 2.53.0",
        "gh": "gh version 2.89.0",
        "node": "v22.22.2",
        "pnpm": "10.33.0",
        "docker": "Docker version 29.3.1",
        "gh auth status": "Logged in",
        "docker info": "ok",
    }
    with patch("scripts.preflight.subprocess.run", side_effect=_make_version_responses(responses)):
        results = preflight("fullstack-ts")

    tool_names = [r.tool for r in results]
    assert "uv" not in tool_names
    assert "xcodegen" not in tool_names


# --- generate_install_script ---


def test_generate_install_script_all_passing(tmp_path):
    results = [
        CheckResult("git", "2.39+", "2.53.0", Status.OK, "xcode-select --install"),
        CheckResult("node", "22.0+", "22.22.2", Status.OK, "brew install fnm && fnm install 22"),
    ]
    assert generate_install_script(results, tmp_path) is None


def test_generate_install_script_with_failures(tmp_path):
    results = [
        CheckResult("git", "2.39+", "2.53.0", Status.OK, "xcode-select --install"),
        CheckResult("pnpm", "10.0+", None, Status.MISSING, "brew install pnpm"),
        CheckResult("docker", "27.0+", "24.0.7", Status.OUTDATED, "brew install --cask docker"),
    ]
    script_path = generate_install_script(results, tmp_path)
    assert script_path is not None
    assert script_path.exists()
    assert script_path.name == "install-deps.sh"

    content = script_path.read_text()
    assert "#!/usr/bin/env bash" in content
    assert "brew install pnpm" in content
    assert "brew install --cask docker" in content
    # Should not include passing tools
    assert "xcode-select" not in content


def test_generate_install_script_is_executable(tmp_path):
    results = [
        CheckResult("pnpm", "10.0+", None, Status.MISSING, "brew install pnpm"),
    ]
    script_path = generate_install_script(results, tmp_path)
    assert script_path is not None
    assert script_path.stat().st_mode & 0o755
