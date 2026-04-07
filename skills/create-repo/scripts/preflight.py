"""Preflight environment checker for create-repo.

Verifies that all required tools are installed and meet minimum version
requirements before scaffolding a project. Generates an install script
for any missing or outdated tools.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"


@dataclass
class CheckResult:
    tool: str
    required_version: str | None
    found_version: str | None
    status: Status
    install_command: str


COMMON_CHECKS: list[dict] = [
    {
        "tool": "git",
        "command": ["git", "--version"],
        "pattern": r"git version (\d+\.\d+(?:\.\d+)?)",
        "min": (2, 39),
        "install": "xcode-select --install",
    },
    {
        "tool": "gh",
        "command": ["gh", "--version"],
        "pattern": r"gh version (\d+\.\d+(?:\.\d+)?)",
        "min": (2, 40),
        "install": "brew install gh",
    },
    {
        "tool": "node",
        "command": ["node", "--version"],
        "pattern": r"v(\d+\.\d+(?:\.\d+)?)",
        "min": (22, 0),
        "install": "brew install fnm && fnm install 22",
    },
    {
        "tool": "pnpm",
        "command": ["pnpm", "--version"],
        "pattern": r"(\d+\.\d+(?:\.\d+)?)",
        "min": (10, 0),
        "install": "brew install pnpm",
    },
    {
        "tool": "docker",
        "command": ["docker", "--version"],
        "pattern": r"Docker version (\d+\.\d+(?:\.\d+)?)",
        "min": (27, 0),
        "install": "brew install --cask docker",
    },
]

TEMPLATE_CHECKS: dict[str, list[dict]] = {
    "fullstack-python": [
        {
            "tool": "uv",
            "command": ["uv", "--version"],
            "pattern": r"uv (\d+\.\d+(?:\.\d+)?)",
            "min": (0, 5),
            "install": "brew install uv",
        },
    ],
    "api-python": [
        {
            "tool": "uv",
            "command": ["uv", "--version"],
            "pattern": r"uv (\d+\.\d+(?:\.\d+)?)",
            "min": (0, 5),
            "install": "brew install uv",
        },
    ],
    "swift-ts": [
        {
            "tool": "xcodegen",
            "command": ["xcodegen", "--version"],
            "pattern": r"Version:?\s*(\d+\.\d+(?:\.\d+)?)",
            "min": None,
            "install": "brew install xcodegen",
        },
    ],
}

# Runtime checks (not version-based — just pass/fail)
RUNTIME_CHECKS: list[dict] = [
    {
        "tool": "gh (authenticated)",
        "command": ["gh", "auth", "status"],
        "success_means": "authenticated",
        "install": "gh auth login",
    },
    {
        "tool": "docker (daemon)",
        "command": ["docker", "info"],
        "success_means": "daemon running",
        "install": "open -a Docker",
    },
]


def parse_version(text: str, pattern: str) -> str | None:
    """Extract a version string from command output using a regex pattern."""
    match = re.search(pattern, text)
    return match.group(1) if match else None


def version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert '1.2.3' to (1, 2, 3)."""
    return tuple(int(p) for p in version_str.split("."))


def run_check(check: dict) -> CheckResult:
    """Run a single version check."""
    try:
        proc = subprocess.run(
            check["command"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        return CheckResult(
            tool=check["tool"],
            required_version=_format_min(check.get("min")),
            found_version=None,
            status=Status.MISSING,
            install_command=check["install"],
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            tool=check["tool"],
            required_version=_format_min(check.get("min")),
            found_version=None,
            status=Status.MISSING,
            install_command=check["install"],
        )

    found = parse_version(output, check["pattern"])
    if not found:
        return CheckResult(
            tool=check["tool"],
            required_version=_format_min(check.get("min")),
            found_version=None,
            status=Status.MISSING,
            install_command=check["install"],
        )

    min_ver = check.get("min")
    if min_ver and version_tuple(found)[:2] < min_ver:
        return CheckResult(
            tool=check["tool"],
            required_version=_format_min(min_ver),
            found_version=found,
            status=Status.OUTDATED,
            install_command=check["install"],
        )

    return CheckResult(
        tool=check["tool"],
        required_version=_format_min(min_ver),
        found_version=found,
        status=Status.OK,
        install_command=check["install"],
    )


def run_runtime_check(check: dict) -> CheckResult:
    """Run a runtime check (success/failure, not version-based)."""
    try:
        proc = subprocess.run(
            check["command"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return CheckResult(
                tool=check["tool"],
                required_version=None,
                found_version=check["success_means"],
                status=Status.OK,
                install_command=check["install"],
            )
        return CheckResult(
            tool=check["tool"],
            required_version=None,
            found_version=None,
            status=Status.MISSING,
            install_command=check["install"],
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return CheckResult(
            tool=check["tool"],
            required_version=None,
            found_version=None,
            status=Status.MISSING,
            install_command=check["install"],
        )


def _format_min(min_ver: tuple[int, ...] | None) -> str | None:
    if min_ver is None:
        return None
    return ".".join(str(v) for v in min_ver) + "+"


def preflight(template: str) -> list[CheckResult]:
    """Run all preflight checks for a given template. Returns list of results."""
    checks = list(COMMON_CHECKS)
    checks.extend(TEMPLATE_CHECKS.get(template, []))

    results = [run_check(c) for c in checks]
    results.extend(run_runtime_check(c) for c in RUNTIME_CHECKS)
    return results


STATUS_SYMBOLS = {
    Status.OK: "\u2705",
    Status.MISSING: "\u274c",
    Status.OUTDATED: "\u26a0\ufe0f ",
}


def print_results(results: list[CheckResult]) -> None:
    """Print a formatted table of check results."""
    tool_width = max(len(r.tool) for r in results)
    ver_width = max(len(r.found_version or "not found") for r in results)

    print(f"\n{'Tool':<{tool_width}}  {'Version':<{ver_width}}  {'Required':<10}  Status")
    print(f"{'-' * tool_width}  {'-' * ver_width}  {'-' * 10}  {'-' * 10}")

    for r in results:
        symbol = STATUS_SYMBOLS[r.status]
        found = r.found_version or "not found"
        required = r.required_version or "any"
        status_line = (
            f"{r.tool:<{tool_width}}  {found:<{ver_width}}"
            f"  {required:<10}  {symbol} {r.status.value}"
        )
        print(status_line)


def generate_install_script(results: list[CheckResult], output_dir: Path) -> Path | None:
    """Generate a shell script to install/upgrade all failing tools.

    Returns the path to the generated script, or None if everything passed.
    """
    failures = [r for r in results if r.status != Status.OK]
    if not failures:
        return None

    lines = [
        "#!/usr/bin/env bash",
        "# Auto-generated by create-repo preflight checker.",
        "# Installs or upgrades missing/outdated tools.",
        "set -euo pipefail",
        "",
        "# Ensure Homebrew is available (most commands use it)",
        "if ! command -v brew &>/dev/null; then",
        '  echo "Homebrew is required but not installed."',
        '  echo "Install it from https://brew.sh and re-run this script."',
        "  exit 1",
        "fi",
        "",
    ]

    for r in failures:
        reason = "missing" if r.status == Status.MISSING else f"outdated ({r.found_version})"
        lines.append(f"echo '==> Installing {r.tool} ({reason})'")
        lines.append(r.install_command)
        lines.append("")

    has_docker = any(r.tool == "docker" for r in failures)
    if has_docker:
        lines.append("echo ''")
        lines.append("echo '┌─────────────────────────────────────────────────────────────┐'")
        lines.append("echo '│  🐳 Docker Desktop may ask about Rosetta on first launch.   │'")
        lines.append("echo '│  If you see a Rosetta installation error, click              │'")
        lines.append("echo '│  \"Disable Rosetta\" — it is not needed on Apple Silicon.      │'")
        lines.append("echo '└─────────────────────────────────────────────────────────────┘'")

    lines.append("echo ''")
    lines.append(
        "echo 'Done! Re-run preflight to verify:"
        " uv run python -m scripts.preflight --template <template>'"
    )

    script_path = output_dir / "install-deps.sh"
    script_path.write_text("\n".join(lines) + "\n")
    script_path.chmod(0o755)
    return script_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight environment checker")
    parser.add_argument(
        "--template",
        required=True,
        help="Template name (e.g. fullstack-ts, fullstack-python)",
    )
    args = parser.parse_args()

    results = preflight(args.template)
    print_results(results)

    script_path = generate_install_script(results, Path.cwd())
    if script_path:
        run_cmd = f"bash {script_path}"
        # Copy the command to clipboard on macOS for easy pasting
        try:
            subprocess.run(["pbcopy"], input=run_cmd, text=True, timeout=5)
            print("\nTo install everything that's missing, run (copied to clipboard):")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("\nTo install everything that's missing, run:")
        print(f"  {run_cmd}")
        sys.exit(1)
    else:
        print("\nAll checks passed!")


if __name__ == "__main__":
    main()
