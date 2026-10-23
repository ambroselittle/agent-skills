#!/usr/bin/env python3
"""Discover installed agents and apply their components from one shared source."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import setup_config
import setup_migrations

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = (
    "skills",
    "pretooluse",
    "notification",
    "message-display",
    "window-title",
    "attribution",
    "mcp",
    "guidance",
    "cli",
)
GROUPS = {"all": COMPONENTS, "hooks": setup_config.HOOK_NAMES}


def selection(arguments: list[str]) -> tuple[set[str], set[str]]:
    selected, excluded = set(), set()
    destination = selected
    for argument in arguments:
        if argument == "--no-clear":
            continue
        if argument == "--without":
            destination = excluded
            continue
        names = GROUPS.get(argument, (argument,))
        if any(name not in COMPONENTS for name in names):
            raise ValueError(f"Unknown component or flag: {argument}")
        destination.update(names)
    return selected or set(COMPONENTS), excluded


def target_home(target: str) -> Path:
    if target == "codex":
        return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return Path.home() / ".claude"


def detected_agents() -> tuple[str, ...]:
    """Empty agent directories alone are not an installed/configured agent."""
    roots = os.environ.get("AGENT_SKILLS_APPLICATION_DIRS")
    app_roots = (
        [Path(path).expanduser() for path in roots.split(os.pathsep) if path]
        if roots is not None
        else [Path("/Applications"), Path.home() / "Applications"]
    )
    found = []
    for agent in ("claude", "codex"):
        home = target_home(agent)
        configs = (
            ("settings.json", "settings.local.json", "CLAUDE.md", "agent-skills.json")
            if agent == "claude"
            else ("config.toml", "AGENTS.md", "hooks.json", "agent-skills.json")
        )
        apps = ("Claude.app",) if agent == "claude" else ("Codex.app",)
        if (
            shutil.which(agent)
            or any((home / name).is_file() for name in configs)
            or any((directory / name).is_dir() for directory in app_roots for name in apps)
        ):
            found.append(agent)
    return tuple(found)


def exclusion_block(config: dict) -> dict:
    raw = config.get("exclude", {})
    if isinstance(raw, dict):
        return raw
    setup_config.normalize_exclusions(config)
    return {}


def target_config(target: str) -> tuple[Path, dict, dict]:
    path = setup_config.config_path()
    common = setup_config.load_json(path)
    config, effective = setup_config.agent_preferences(common, target)
    return path, config, effective


def save_target_config(target: str, config: dict) -> None:
    path = setup_config.config_path()
    common = setup_config.load_json(path)
    agents = common.setdefault("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("agents must be an object")
    agents[target] = config
    setup_config.save_json(path, common)


def guidance_path(target: str) -> Path:
    return target_home(target) / ("AGENTS.md" if target == "codex" else "CLAUDE.md")


def refresh_guidance(target: str, dry_run: bool = False) -> None:
    """Refresh this agent and every other already-managed guidance block."""
    targets = [target]
    for other in ("claude", "codex"):
        path = guidance_path(other)
        if other != target and path.exists() and setup_config.GUIDANCE_OPEN_TAG in path.read_text():
            targets.append(other)
    for agent in targets:
        _, config, effective = target_config(agent)
        exclusions = setup_config.normalize_exclusions(effective).get("guidance", set())
        remove = bool({"all", "core"} & exclusions)
        path = guidance_path(agent)
        print(
            f"{agent.title()}: {'remove' if remove else 'install'} managed guidance block in {path}"
        )
        if dry_run:
            continue
        if remove:
            setup_config.cmd_guidance(argparse.Namespace(action="remove", claude_md=str(path)))
            continue
        user = None
        if "personal" in exclusions:
            setup_config.skip("Personal template excluded")
        else:
            user = (
                os.environ.get("AGENT_SKILLS_USER")
                or effective.get("user")
                or effective.get("gh_username")
            )
            if not user:
                try:
                    lookup = subprocess.run(
                        ["gh", "api", "user", "--jq", ".login"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if lookup.returncode == 0:
                        user = lookup.stdout.strip() or None
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if user and config.get("user") != user:
                setup_config.guidance_content(ROOT, agent, user)
                config["user"] = user
                save_target_config(agent, config)
        setup_config.cmd_guidance(
            argparse.Namespace(
                action="upsert",
                claude_md=str(path),
                content_text=setup_config.guidance_content(ROOT, agent, user).rstrip("\n"),
            )
        )


def source_selection() -> tuple[Path, set[str] | None]:
    """Keep unchanged skills on the primary checkout when using a worktree."""

    def git(*arguments):
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    common = git("rev-parse", "--git-common-dir")
    if not common:
        return ROOT, None
    directory = Path(common)
    if not directory.is_absolute():
        directory = ROOT / directory
    primary = directory.resolve().parent
    if primary == ROOT:
        return ROOT, None
    names = set()
    for arguments in (
        ("diff", "--name-only", "main...", "--", "skills/"),
        ("diff", "--name-only", "--", "skills/"),
        ("ls-files", "--others", "--exclude-standard", "--", "skills/"),
    ):
        for name in git(*arguments).splitlines():
            parts = Path(name).parts
            if len(parts) > 1 and parts[0] == "skills":
                names.add(parts[1])
    if names:
        names.add("shared")
    return primary, names


def install_shared_sources(dry_run: bool) -> None:
    """Canonical aliases share maintained sources without flattening or copies."""
    shared = Path.home() / ".agent-skills"
    manifest_path = shared / "resource-links.json"
    manifest = setup_config.load_json(manifest_path)
    primary, changed = source_selection()
    catalog = json.loads((ROOT / "skills/compatibility.json").read_text())
    desired = {shared / "source": ROOT, shared / "scripts/python": Path(sys.executable).resolve()}
    for source in sorted((ROOT / "skills").iterdir()):
        if not source.is_dir() or source.name not in set(catalog) | {"shared"}:
            continue
        if changed is not None and source.name not in changed:
            baseline = primary / "skills" / source.name
            if baseline.is_dir():
                source = baseline
        desired[shared / "skills" / source.name] = source
        if (source / "scripts").is_dir():
            desired[shared / "scripts" / source.name] = source / "scripts"
    for path, source in desired.items():
        key = str(path.relative_to(shared))
        if path.is_symlink() and path.readlink() == source:
            manifest[key] = str(source)
            continue
        if path.exists() or path.is_symlink():
            if not path.is_symlink() or str(path.readlink()) != manifest.get(key):
                raise ValueError(f"Shared installation path is not installer-owned: {path}")
        print(f"  Shared source: {path} → {source}")
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.unlink(missing_ok=True)
            path.symlink_to(source, target_is_directory=source.is_dir())
            manifest[key] = str(source)
    current = {str(path.relative_to(shared)) for path in desired}
    for key in set(manifest) - current:
        parts = Path(key).parts
        if (
            len(parts) != 2
            or parts[0] not in ("skills", "scripts")
            or not isinstance(manifest[key], str)
        ):
            continue  # Unknown manifest metadata is not an obsolete alias.
        path = shared / key
        if path.is_symlink() and str(path.readlink()) == manifest[key]:
            print(f"  Remove obsolete owned alias: {path}")
            if not dry_run:
                path.unlink()
        if not dry_run:
            del manifest[key]
    if not dry_run and setup_config.load_json(manifest_path) != manifest:
        setup_config.save_json(manifest_path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("claude", "codex", "both"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--shell-only", action="store_true", help="limit Codex denial checks to shell calls"
    )
    parser.add_argument("--refresh-guidance", action="store_true", help=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args()
    if args.list:
        for component in COMPONENTS:
            supported = component in ("skills", "pretooluse", "guidance")
            print(
                f"{component}: Claude supported; Codex "
                f"{'supported' if supported else 'Claude-only'}"
            )
        print("hooks: pretooluse + notification + message-display + window-title")
        print("all: every component")
        return 0
    try:
        selected, excluded = selection(remaining)
        targets = (
            (("claude", "codex") if args.target == "both" else (args.target,))
            if args.target
            else detected_agents()
        )
        if not targets:
            print(
                "No supported agents detected. Install or configure Claude or Codex, "
                "or select --target explicitly. Nothing changed."
            )
            return 0
        if not args.dry_run:
            setup_migrations.migrate(ROOT, source_selection()[0])
        if args.refresh_guidance:
            for target in targets:
                refresh_guidance(target, args.dry_run)
            return 0
        if not args.dry_run:
            install_shared_sources(False)
        for target in targets:
            path, config, effective = target_config(target)
            changed = []
            for component in sorted(excluded):
                changed.extend(
                    setup_config.add_exclusions(
                        config, setup_config.COMPONENT_EXCLUSIONS[component]
                    )
                )
            if changed and not args.dry_run:
                print("Persisting exclusions")
                save_target_config(target, config)
                print(f"  Saved to {path} — edit its exclude key to undo.")
            effective["exclude"] = {**exclusion_block(effective), **exclusion_block(config)}
            exclusions = setup_config.normalize_exclusions(effective)
            if exclusions:
                summary = " ".join(
                    f"{key}:{','.join(sorted(value))}" for key, value in sorted(exclusions.items())
                )
                print(f"  Excluded ({path}): {summary}")
            claude_components = []
            for component in COMPONENTS:
                if component not in selected | excluded:
                    continue
                category, name = setup_config.COMPONENT_EXCLUSIONS[component][0]
                excluded_names = exclusions.get(category, set())
                remove = "all" in excluded_names or name in excluded_names
                action = "remove" if remove else "install"
                if args.dry_run:
                    print(f"{target.title()}: {action} {component}")
                elif component == "skills":
                    setup_config.agent_skills(
                        ROOT,
                        target,
                        target_home(target),
                        excluded_names,
                        False,
                        primary_root=source_selection()[0],
                    )
                elif component == "guidance":
                    refresh_guidance(target)
                elif target == "claude":
                    claude_components.append(component)
                elif component == "pretooluse":
                    setup_config.cmd_codex_policy(
                        argparse.Namespace(
                            action=action,
                            codex_home=str(target_home(target)),
                            source=str(ROOT / "hooks/PreToolUse"),
                            shell_only=args.shell_only,
                        )
                    )
                elif component == "window-title":
                    setup_config.codex_window_titles(target_home(target), False)
                else:
                    print(
                        f"Codex: {component} is Claude-only; existing Codex settings are left alone"
                    )
            if claude_components:
                result = subprocess.run(
                    ["bash", str(ROOT / "setup.sh"), *claude_components, "--no-clear"],
                    env={
                        **os.environ,
                        "AGENT_SKILLS_INTERNAL_CLAUDE_COMPONENTS": "1",
                        "AGENT_SKILLS_SETUP_AGENT": "claude",
                        "AGENT_SKILLS_CONFIG": str(path),
                        "AGENT_SKILLS_PYTHON": str(Path.home() / ".agent-skills/scripts/python"),
                    },
                    check=False,
                )
                if result.returncode:
                    return result.returncode
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
