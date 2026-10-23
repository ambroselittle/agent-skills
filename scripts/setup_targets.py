#!/usr/bin/env python3
"""Target selection for setup.sh; configuration writes stay in setup_config."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import setup_config

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


def exclusion_block(config: dict) -> dict:
    raw = config.get("exclude", {})
    if isinstance(raw, dict):
        return raw
    # Reuse the established warning instead of failing before normalization.
    setup_config.normalize_exclusions(config)
    return {}


def target_config(target: str) -> tuple[Path, dict, dict]:
    """Read each agent's config; Codex overrides inherited Claude categories."""
    common_path = setup_config.config_path()
    common = setup_config.load_json(common_path)
    if target == "claude":
        return common_path, common, common
    path = target_home(target) / "agent-skills.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    effective = {
        **common,
        **config,
        "exclude": {**exclusion_block(common), **exclusion_block(config)},
    }
    return path, config, effective


def guidance_path(target: str) -> Path:
    return target_home(target) / ("AGENTS.md" if target == "codex" else "CLAUDE.md")


def refresh_guidance(target: str, dry_run: bool = False) -> None:
    """Refresh the requested agent and other agents with our managed block."""
    targets = [target]
    for other in ("claude", "codex"):
        path = guidance_path(other)
        if other != target and path.exists() and setup_config.GUIDANCE_OPEN_TAG in path.read_text():
            targets.append(other)
    for agent in targets:
        config_path, config, effective = target_config(agent)
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
                # Validate before persisting the selection.
                setup_config.guidance_content(ROOT, agent, user)
                config["user"] = user
                setup_config.save_json(config_path, config)
        setup_config.cmd_guidance(
            argparse.Namespace(
                action="upsert",
                claude_md=str(path),
                content_text=setup_config.guidance_content(ROOT, agent, user).rstrip("\n"),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("claude", "codex", "both"), default="claude")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", help="list components and Codex support")
    parser.add_argument(
        "--shell-only", action="store_true", help="install only shell approval coverage"
    )
    parser.add_argument("--refresh-guidance", action="store_true", help=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args()
    if args.list:
        for component in COMPONENTS:
            support = (
                "supported" if component in ("skills", "pretooluse", "guidance") else "Claude-only"
            )
            print(f"{component}: Codex {support}")
        return 0
    try:
        selected, excluded = selection(remaining)
    except ValueError as error:
        parser.error(str(error))
    targets = ("claude", "codex") if args.target == "both" else (args.target,)
    if args.refresh_guidance:
        for target in targets:
            refresh_guidance(target, args.dry_run)
        return 0
    for target in targets:
        config_path, config, effective = target_config(target)
        for component in excluded:
            setup_config.add_exclusions(config, setup_config.COMPONENT_EXCLUSIONS[component])
        effective["exclude"] = {**exclusion_block(effective), **exclusion_block(config)}
        exclusions = setup_config.normalize_exclusions(effective)
        if target == "claude":
            if args.dry_run:
                for component in sorted(selected | excluded):
                    names = setup_config.COMPONENT_EXCLUSIONS[component]
                    remove = all(
                        "all" in exclusions.get(category, set())
                        or name in exclusions.get(category, set())
                        for category, name in names
                    )
                    print(f"Claude: {'remove' if remove else 'install'} {component}")
                print("  Managed locations: ~/.claude/{skills,hooks,settings.json,CLAUDE.md}")
                continue
            result = subprocess.run(["bash", str(ROOT / "setup.sh"), *remaining], check=False)
            if result.returncode:
                return result.returncode
            continue
        home = target_home(target)
        if excluded and not args.dry_run:
            setup_config.save_json(config_path, config)
        for component in sorted(selected | excluded):
            category, name = setup_config.COMPONENT_EXCLUSIONS[component][0]
            excluded_names = exclusions.get(category, set())
            remove = "all" in excluded_names or name in excluded_names
            action = "remove" if remove else "install"
            if component == "pretooluse":
                if args.dry_run:
                    print(
                        f"Codex: {action} policy adapter, engine and rules under {home / 'hooks'}"
                    )
                    print(f"  Merge tool hooks into {home / 'hooks.json'}; preserve other hooks")
                    continue
                setup_config.cmd_codex_policy(
                    argparse.Namespace(
                        action=action,
                        codex_home=str(home),
                        source=str(ROOT / "hooks/PreToolUse"),
                        shell_only=args.shell_only,
                    )
                )
            elif component == "skills":
                setup_config.codex_skills(ROOT, home, excluded_names, args.dry_run)
            elif component == "guidance":
                refresh_guidance(target, args.dry_run)
            elif component == "window-title":
                setup_config.codex_window_titles(home, args.dry_run)
            else:
                print(f"Codex: {component} is Claude-only; existing Codex settings are left alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
