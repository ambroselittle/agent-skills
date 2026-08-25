#!/usr/bin/env python3
"""Config and settings primitives for setup.sh.

setup.sh shells out to this script for everything that needs judgment beyond
copying files: reading the ``exclude`` block from ``~/.claude/agent-skills.json``,
persisting ``--without``, and every edit to ``~/.claude/settings.json``,
``~/.claude/CLAUDE.md``, and the shell rc file. Each install primitive has an
inverse so an excluded component can be removed with the same tested code that
installed it.

Stdlib only — setup.sh must not gain a dependency.

Usage (each prints the same status lines setup.sh used to print inline):

    setup_config.py exclusions
    setup_config.py add-exclusion <component>
    setup_config.py hook register|unregister <settings.json> <event> <command> [--timeout N]
    setup_config.py permissions merge|remove <settings.json> <rules.json>
    setup_config.py statusline set|unset <settings.json> <command>
    setup_config.py env set|unset <settings.json> <KEY> <value>
    setup_config.py attribution set|unset <settings.json> <key>...
    setup_config.py guidance upsert|remove <CLAUDE.md> [<content-file>|-]
    setup_config.py rcfence upsert|remove <rcfile> [<block-file>|-]

The config path defaults to ``~/.claude/agent-skills.json`` and can be overridden
with the ``AGENT_SKILLS_CONFIG`` environment variable (tests rely on this).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path

# --------------------------------------------------------------------------- #
# Output helpers — match setup.sh's ok/skip/warn styling                      #
# --------------------------------------------------------------------------- #

_GREEN = "\033[32m"
_DIM = "\033[2m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {_GREEN}✓{_RESET} {msg}")


def skip(msg: str) -> None:
    print(f"  {_DIM}· {msg}{_RESET}")


def warn(msg: str) -> None:
    print(f"  {_YELLOW}⚠ {msg}{_RESET}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Exclusion schema                                                            #
# --------------------------------------------------------------------------- #

ALL = "all"

HOOK_NAMES = ("pretooluse", "notification", "message-display", "window-title")
GUIDANCE_NAMES = ("core", "personal")
ATTRIBUTION_NAMES = ("sessionUrl", "commit", "pr")
CLI_NAMES = ("claude-resume", "reclaude")

# Exclusion key → the names it accepts. ``None`` means an open set (skill
# directory names, MCP server names) that setup.sh validates against what it
# actually has on disk.
EXCLUSION_KEYS: dict[str, tuple[str, ...] | None] = {
    "hooks": HOOK_NAMES,
    "mcp": None,
    "guidance": GUIDANCE_NAMES,
    "skills": None,
    "attribution": ATTRIBUTION_NAMES,
    "cli": CLI_NAMES,
}

# Skills that other skills depend on and therefore cannot be excluded.
UNEXCLUDABLE_SKILLS = ("shared",)

# setup.sh component (or group) → the exclusion entries ``--without`` persists.
COMPONENT_EXCLUSIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "pretooluse": (("hooks", "pretooluse"),),
    "notification": (("hooks", "notification"),),
    "message-display": (("hooks", "message-display"),),
    "window-title": (("hooks", "window-title"),),
    "hooks": tuple(("hooks", name) for name in HOOK_NAMES),
    "skills": (("skills", ALL),),
    "mcp": (("mcp", ALL),),
    "guidance": (("guidance", ALL),),
    "attribution": (("attribution", ALL),),
    "cli": (("cli", ALL),),
}

# Attribution keys and the values setup.sh writes for them.
ATTRIBUTION_DESIRED: dict[str, object] = {"sessionUrl": False, "commit": "", "pr": ""}

GUIDANCE_OPEN_TAG = "<agent-skills-guidance>"
GUIDANCE_CLOSE_TAG = "</agent-skills-guidance>"

RCFENCE_BEGIN = "# BEGIN agent-skills-aliases"
RCFENCE_END = "# END agent-skills-aliases"


# --------------------------------------------------------------------------- #
# JSON file helpers                                                           #
# --------------------------------------------------------------------------- #


def config_path() -> Path:
    override = os.environ.get("AGENT_SKILLS_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "agent-skills.json"


def load_json(path: Path) -> dict:
    """Read a JSON object, treating a missing or malformed file as empty."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict) -> None:
    """Write with the exact formatting setup.sh has always used (indent=2 + newline)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# --------------------------------------------------------------------------- #
# exclusions / add-exclusion                                                  #
# --------------------------------------------------------------------------- #


def normalize_exclusions(config: dict) -> dict[str, set[str]]:
    """Return ``{key: {names}}`` from a config's ``exclude`` block.

    ``all`` in a list wins over every other entry in that list. Unknown keys,
    unknown names in a closed set, and unexcludable skills produce a warning
    and are dropped — a typo in the config must never abort setup.
    """
    raw = config.get("exclude", {})
    if not isinstance(raw, dict):
        if raw:
            warn('exclude must be an object of lists — ignoring "exclude"')
        return {}

    result: dict[str, set[str]] = {}
    for key, value in raw.items():
        if key not in EXCLUSION_KEYS:
            warn(f'unknown exclude key "{key}" — ignoring')
            continue
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            warn(f"exclude.{key} must be a list — ignoring")
            continue

        names = {str(v) for v in value}
        if ALL in names:
            result[key] = {ALL}
            continue

        allowed = EXCLUSION_KEYS[key]
        kept: set[str] = set()
        for name in names:
            if allowed is not None and name not in allowed:
                warn(f'unknown exclude.{key} entry "{name}" — ignoring')
                continue
            if key == "skills" and name in UNEXCLUDABLE_SKILLS:
                warn(f'"{name}" cannot be excluded (other skills depend on it) — ignoring')
                continue
            kept.add(name)
        if kept:
            result[key] = kept
    return result


def cmd_exclusions(_: argparse.Namespace) -> int:
    for key, names in sorted(normalize_exclusions(load_json(config_path())).items()):
        for name in sorted(names):
            print(f"{key}={name}")
    return 0


def add_exclusions(config: dict, entries: Iterable[tuple[str, str]]) -> list[str]:
    """Merge ``(key, name)`` pairs into ``config['exclude']``; return what changed."""
    exclude = config.setdefault("exclude", {})
    if not isinstance(exclude, dict):
        exclude = config["exclude"] = {}
    changed: list[str] = []
    for key, name in entries:
        current = exclude.get(key)
        if isinstance(current, str):
            current = [current]
        if not isinstance(current, list):
            current = []
        if ALL in current or name in current:
            continue
        if name == ALL:
            current = [ALL]
        else:
            current = [*current, name]
        exclude[key] = current
        changed.append(f"{key}: {name}")
    return changed


def cmd_add_exclusion(args: argparse.Namespace) -> int:
    entries = COMPONENT_EXCLUSIONS.get(args.component)
    if entries is None:
        warn(f'unknown component "{args.component}" — nothing persisted')
        return 1
    path = config_path()
    config = load_json(path)
    changed = add_exclusions(config, entries)
    if changed:
        save_json(path, config)
        for entry in changed:
            ok(f"exclude.{entry}")
    else:
        skip(f"{args.component} already excluded in {path}")
    return 0


# --------------------------------------------------------------------------- #
# hook register / unregister                                                  #
# --------------------------------------------------------------------------- #


def _find_hook(entries: list, command: str) -> dict | None:
    return next(
        (h for entry in entries for h in entry.get("hooks", []) if command in h.get("command", "")),
        None,
    )


def hook_register(settings: dict, event: str, command: str, timeout: int | None) -> bool:
    """Register ``command`` under ``event``; return True when settings changed."""
    entries = settings.setdefault("hooks", {}).setdefault(event, [])
    desired: dict = {"type": "command", "command": command}
    if timeout:
        desired["timeout"] = timeout
    existing = _find_hook(entries, command)
    if existing == desired:
        return False
    if existing is None:
        entries.append({"hooks": [desired]})
    else:
        existing.clear()
        existing.update(desired)
    return True


def hook_unregister(settings: dict, event: str, command: str) -> bool:
    """Remove every ``command`` hook under ``event``, pruning empties; True if changed."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict) or event not in hooks:
        return False
    entries = hooks[event]
    changed = False
    for entry in entries:
        kept = [h for h in entry.get("hooks", []) if command not in h.get("command", "")]
        if len(kept) != len(entry.get("hooks", [])):
            entry["hooks"] = kept
            changed = True
    if not changed:
        return False
    hooks[event] = [e for e in entries if e.get("hooks")]
    if not hooks[event]:
        del hooks[event]
    if not hooks:
        del settings["hooks"]
    return True


def cmd_hook(args: argparse.Namespace) -> int:
    path = Path(args.settings)
    settings = load_json(path)
    if args.action == "register":
        if hook_register(settings, args.event, args.hook_command, args.timeout):
            save_json(path, settings)
            ok(f"{args.event} hook registered in settings.json")
        else:
            skip(f"{args.event} hook already registered in settings.json")
    else:
        if hook_unregister(settings, args.event, args.hook_command):
            save_json(path, settings)
            ok(f"{args.event} hook removed from settings.json")
        else:
            skip(f"{args.event} hook not present in settings.json")
    return 0


# --------------------------------------------------------------------------- #
# permissions merge / remove                                                  #
# --------------------------------------------------------------------------- #


def permissions_merge(settings: dict, rules: dict) -> tuple[int, int, int]:
    """Union repo allow/deny into settings, subtracting retired rules.

    Returns ``(new_allow, new_deny, removed_count)`` for reporting.
    """
    perms = settings.setdefault("permissions", {})
    removed = set(rules.get("removed", []))
    existing_allow = set(perms.get("allow", []))
    repo_allow = set(rules.get("allow", []))
    perms["allow"] = sorted((existing_allow | repo_allow) - removed)
    existing_deny = set(perms.get("deny", []))
    repo_deny = set(rules.get("deny", []))
    perms["deny"] = sorted((existing_deny | repo_deny) - removed)
    return (
        len(repo_allow - existing_allow),
        len(repo_deny - existing_deny),
        len(removed & (existing_allow | existing_deny)),
    )


def permissions_remove(settings: dict, rules: dict) -> tuple[int, int]:
    """Subtract repo allow/deny (and retired rules) from settings; return counts removed."""
    perms = settings.get("permissions")
    if not isinstance(perms, dict):
        return (0, 0)
    ours = set(rules.get("removed", []))
    allow_ours = ours | set(rules.get("allow", []))
    deny_ours = ours | set(rules.get("deny", []))
    existing_allow = set(perms.get("allow", []))
    existing_deny = set(perms.get("deny", []))
    removed_allow = existing_allow & allow_ours
    removed_deny = existing_deny & deny_ours
    if removed_allow:
        perms["allow"] = sorted(existing_allow - allow_ours)
    if removed_deny:
        perms["deny"] = sorted(existing_deny - deny_ours)
    for name in ("allow", "deny"):
        if name in perms and not perms[name]:
            del perms[name]
    if not perms:
        del settings["permissions"]
    return (len(removed_allow), len(removed_deny))


def cmd_permissions(args: argparse.Namespace) -> int:
    path = Path(args.settings)
    settings = load_json(path)
    with open(args.rules) as f:
        rules = json.load(f)
    if args.action == "merge":
        new_allow, new_deny, removed_count = permissions_merge(settings, rules)
        save_json(path, settings)
        if new_allow or new_deny:
            ok(f"{new_allow} allow + {new_deny} deny rules added")
        else:
            skip(
                f"All {len(rules.get('allow', []))} allow + "
                f"{len(rules.get('deny', []))} deny rules already present"
            )
        if removed_count:
            ok(f"{removed_count} retired rules removed")
    else:
        removed_allow, removed_deny = permissions_remove(settings, rules)
        if removed_allow or removed_deny:
            save_json(path, settings)
            ok(f"{removed_allow} allow + {removed_deny} deny rules removed")
        else:
            skip("No built-in permission rules present")
    return 0


# --------------------------------------------------------------------------- #
# statusline set / unset                                                      #
# --------------------------------------------------------------------------- #


def _statusline_desired(command: str) -> dict:
    return {"type": "command", "command": command}


def statusline_set(settings: dict, command: str) -> bool:
    desired = _statusline_desired(command)
    if settings.get("statusLine") == desired:
        return False
    settings["statusLine"] = desired
    return True


def statusline_unset(settings: dict, command: str) -> bool:
    """Drop ``statusLine`` only when it still holds our value."""
    if settings.get("statusLine") != _statusline_desired(command):
        return False
    del settings["statusLine"]
    return True


def cmd_statusline(args: argparse.Namespace) -> int:
    path = Path(args.settings)
    settings = load_json(path)
    if args.action == "set":
        if statusline_set(settings, args.status_command):
            save_json(path, settings)
            ok("Status line registered in settings.json")
        else:
            skip("Status line already registered in settings.json")
    else:
        if statusline_unset(settings, args.status_command):
            save_json(path, settings)
            ok("Status line removed from settings.json")
        else:
            skip("Status line not ours (or absent) — left alone")
    return 0


# --------------------------------------------------------------------------- #
# env set / unset                                                             #
# --------------------------------------------------------------------------- #


def env_set(settings: dict, key: str, value: str) -> bool:
    env = settings.setdefault("env", {})
    if env.get(key) == value:
        return False
    env[key] = value
    return True


def env_unset(settings: dict, key: str, value: str) -> bool:
    """Drop ``env[key]`` only when it still holds our value."""
    env = settings.get("env")
    if not isinstance(env, dict) or env.get(key) != value:
        return False
    del env[key]
    if not env:
        del settings["env"]
    return True


def cmd_env(args: argparse.Namespace) -> int:
    path = Path(args.settings)
    settings = load_json(path)
    if args.action == "set":
        if env_set(settings, args.key, args.value):
            save_json(path, settings)
            ok(f"{args.key}={args.value} set in settings.json")
        else:
            skip(f"{args.key} already set in settings.json")
    else:
        if env_unset(settings, args.key, args.value):
            save_json(path, settings)
            ok(f"{args.key} removed from settings.json")
        else:
            skip(f"{args.key} not ours (or absent) — left alone")
    return 0


# --------------------------------------------------------------------------- #
# attribution set / unset                                                     #
# --------------------------------------------------------------------------- #


def attribution_set(settings: dict, keys: Iterable[str]) -> list[str]:
    """Write our value for each key; return the keys that changed."""
    attribution = settings.setdefault("attribution", {})
    changed = []
    for key in keys:
        desired = ATTRIBUTION_DESIRED[key]
        if attribution.get(key) != desired:
            attribution[key] = desired
            changed.append(key)
    return changed


def attribution_unset(settings: dict, keys: Iterable[str]) -> list[str]:
    """Delete each key that still holds our value; return the keys removed."""
    attribution = settings.get("attribution")
    if not isinstance(attribution, dict):
        return []
    removed = []
    for key in keys:
        if key in attribution and attribution[key] == ATTRIBUTION_DESIRED[key]:
            del attribution[key]
            removed.append(key)
    if not attribution:
        del settings["attribution"]
    return removed


def cmd_attribution(args: argparse.Namespace) -> int:
    unknown = [k for k in args.keys if k not in ATTRIBUTION_DESIRED]
    if unknown:
        warn(f"unknown attribution key(s): {', '.join(unknown)}")
        return 1
    path = Path(args.settings)
    settings = load_json(path)
    if args.action == "set":
        changed = attribution_set(settings, args.keys)
        if changed:
            save_json(path, settings)
            ok(f"Auto-attribution disabled ({', '.join(changed)})")
        else:
            skip("Auto-attribution already disabled")
    else:
        removed = attribution_unset(settings, args.keys)
        if removed:
            save_json(path, settings)
            ok(f"Auto-attribution restored to Claude Code defaults ({', '.join(removed)})")
        else:
            skip("Auto-attribution keys not ours (or absent) — left alone")
    return 0


# --------------------------------------------------------------------------- #
# guidance upsert / remove                                                    #
# --------------------------------------------------------------------------- #


def guidance_upsert(existing: str | None, content: str) -> tuple[str, str]:
    """Return ``(updated_text, action)`` for the fenced guidance block."""
    fenced = f"{GUIDANCE_OPEN_TAG}\n{content}\n{GUIDANCE_CLOSE_TAG}"
    if existing is None:
        return fenced + "\n", "Created"
    if GUIDANCE_OPEN_TAG in existing and GUIDANCE_CLOSE_TAG in existing:
        before = existing[: existing.index(GUIDANCE_OPEN_TAG)]
        after = existing[existing.index(GUIDANCE_CLOSE_TAG) + len(GUIDANCE_CLOSE_TAG) :]
        return before + fenced + after, "Updated"
    if GUIDANCE_OPEN_TAG in existing or GUIDANCE_CLOSE_TAG in existing:
        warn("Orphaned tag found — prepending fresh block")
    return fenced + "\n\n" + existing, "Prepended"


def guidance_remove(existing: str) -> str | None:
    """Return the text without the fenced block, or None when nothing is ours."""
    if GUIDANCE_OPEN_TAG not in existing or GUIDANCE_CLOSE_TAG not in existing:
        return None
    before = existing[: existing.index(GUIDANCE_OPEN_TAG)]
    after = existing[existing.index(GUIDANCE_CLOSE_TAG) + len(GUIDANCE_CLOSE_TAG) :]
    if not before.strip():
        # We prepended (or created) this block: drop the separator we added too.
        return after.lstrip("\n")
    return before + after


def _read_content(source: str | None) -> str:
    if source is None or source == "-":
        return sys.stdin.read()
    return Path(source).read_text()


def cmd_guidance(args: argparse.Namespace) -> int:
    path = Path(args.claude_md)
    if args.action == "upsert":
        content = _read_content(args.content)
        existing = path.read_text() if path.exists() else None
        updated, action = guidance_upsert(existing, content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated)
        ok(f"{action} guidance block in {path}")
        return 0

    if not path.exists():
        skip(f"{path} not present — nothing to remove")
        return 0
    remainder = guidance_remove(path.read_text())
    if remainder is None:
        skip(f"No guidance block in {path} — left alone")
        return 0
    if remainder.strip():
        path.write_text(remainder)
        ok(f"Removed guidance block from {path}")
    else:
        path.unlink()
        ok(f"Removed {path} (it held only the guidance block)")
    return 0


# --------------------------------------------------------------------------- #
# rcfence upsert / remove                                                     #
# --------------------------------------------------------------------------- #


def _fence_span(lines: list[str]) -> tuple[int, int] | None:
    begin = next((i for i, line in enumerate(lines) if line.startswith(RCFENCE_BEGIN)), None)
    if begin is None:
        return None
    end = next((i for i in range(begin, len(lines)) if lines[i].startswith(RCFENCE_END)), None)
    if end is None:
        return None
    return begin, end


def rcfence_upsert(existing: str, block: str) -> tuple[str, str]:
    """Replace or append the managed alias fence; return ``(text, action)``."""
    block_lines = block.strip("\n").splitlines()
    lines = existing.splitlines()
    span = _fence_span(lines)
    if span is not None:
        begin, end = span
        if lines[begin : end + 1] == block_lines:
            return existing, "unchanged"
        lines[begin : end + 1] = block_lines
        return "\n".join(lines) + "\n", "updated"
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(block_lines)
    return "\n".join(lines) + "\n", "added"


def rcfence_remove(existing: str) -> str | None:
    """Drop the managed fence (and the blank line before it); None when absent."""
    lines = existing.splitlines()
    span = _fence_span(lines)
    if span is None:
        return None
    begin, end = span
    del lines[begin : end + 1]
    if begin > 0 and begin <= len(lines) and not lines[begin - 1].strip():
        if begin == len(lines) or not lines[begin].strip():
            del lines[begin - 1]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def cmd_rcfence(args: argparse.Namespace) -> int:
    path = Path(args.rcfile)
    if not path.exists():
        skip(f"{path.name} not present — shell aliases left alone")
        return 0
    existing = path.read_text()
    if args.action == "upsert":
        updated, action = rcfence_upsert(existing, _read_content(args.block))
        if action == "unchanged":
            skip(f"Shell aliases already current in {path.name}")
        else:
            path.write_text(updated)
            ok(f"Shell aliases {action} in {path.name}")
        return 0
    remainder = rcfence_remove(existing)
    if remainder is None:
        skip(f"No agent-skills aliases in {path.name}")
    else:
        path.write_text(remainder)
        ok(f"Shell aliases removed from {path.name}")
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("exclusions", help="print normalized exclusions as key=name lines")

    p = sub.add_parser("add-exclusion", help="persist a --without component into the config")
    p.add_argument("component", choices=sorted(COMPONENT_EXCLUSIONS))

    p = sub.add_parser("hook")
    p.add_argument("action", choices=["register", "unregister"])
    p.add_argument("settings")
    p.add_argument("event")
    p.add_argument("hook_command")
    p.add_argument("--timeout", type=int, default=None)

    p = sub.add_parser("permissions")
    p.add_argument("action", choices=["merge", "remove"])
    p.add_argument("settings")
    p.add_argument("rules")

    p = sub.add_parser("statusline")
    p.add_argument("action", choices=["set", "unset"])
    p.add_argument("settings")
    p.add_argument("status_command")

    p = sub.add_parser("env")
    p.add_argument("action", choices=["set", "unset"])
    p.add_argument("settings")
    p.add_argument("key")
    p.add_argument("value")

    p = sub.add_parser("attribution")
    p.add_argument("action", choices=["set", "unset"])
    p.add_argument("settings")
    p.add_argument("keys", nargs="+")

    p = sub.add_parser("guidance")
    p.add_argument("action", choices=["upsert", "remove"])
    p.add_argument("claude_md")
    p.add_argument("content", nargs="?")

    p = sub.add_parser("rcfence")
    p.add_argument("action", choices=["upsert", "remove"])
    p.add_argument("rcfile")
    p.add_argument("block", nargs="?")

    return parser


COMMANDS = {
    "exclusions": cmd_exclusions,
    "add-exclusion": cmd_add_exclusion,
    "hook": cmd_hook,
    "permissions": cmd_permissions,
    "statusline": cmd_statusline,
    "env": cmd_env,
    "attribution": cmd_attribution,
    "guidance": cmd_guidance,
    "rcfence": cmd_rcfence,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
