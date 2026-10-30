#!/usr/bin/env python3
"""Config and settings primitives for setup.sh.

setup.sh shells out to this script for everything that needs judgment beyond
copying files: reading shared preferences from ``~/.agent-skills/config.json``,
persisting ``--without``, and every edit to ``~/.claude/settings.json``,
the agents' managed guidance blocks, and the shell rc file. Each primitive has an
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

The config path defaults to ``~/.agent-skills/config.json`` and can be overridden
with ``AGENT_SKILLS_CONFIG``. Per-agent preferences under ``agents`` override
shared defaults; managed guidance retains personal text outside its block.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import tempfile
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
    return Path.home() / ".agent-skills" / "config.json"


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
    # Keep dotfiles-managed symlinks connected to their source.
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        try:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            if path.exists():
                temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


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


def agent_preferences(common: dict, agent: str) -> tuple[dict, dict]:
    """Return an agent's writable overrides and its effective shared preferences."""
    agents = common.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("agents must be an object")
    overrides = agents.get(agent, {})
    if not isinstance(overrides, dict):
        raise ValueError(f"agents.{agent} must be an object")

    def exclusions(config: dict) -> dict:
        value = config.get("exclude", {})
        if isinstance(value, dict):
            return value
        normalize_exclusions(config)
        return {}

    return overrides, {
        **common,
        **overrides,
        "exclude": {**exclusions(common), **exclusions(overrides)},
    }


def cmd_exclusions(_: argparse.Namespace) -> int:
    config = load_json(config_path())
    agent = os.environ.get("AGENT_SKILLS_SETUP_AGENT")
    if agent:
        _, config = agent_preferences(config, agent)
    for key, names in sorted(normalize_exclusions(config).items()):
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


def cmd_codex_policy(args: argparse.Namespace) -> int:
    """Install explicit-deny enforcement; native permissions retain all approvals."""
    import setup_migrations

    home = Path(args.codex_home).expanduser()
    source = Path(args.source)
    settings_path = home / "hooks.json"
    # Unlike the legacy tolerant reader, don't overwrite malformed user config.
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    hook_dir = home / "hooks"
    target = hook_dir / "agent-skills-policy"
    entry = hook_dir / "agent-skills-permission-request.py"
    runtime = Path.home() / ".agent-skills/scripts/python"
    command = f"{shlex.quote(str(runtime))} {shlex.quote(str(entry))}"
    # Reconcile existing definitions, including snapshots installed before the
    # shared runtime existed. Their cached PermissionRequest events now defer.
    setup_migrations.remove_owned_approval_hooks(home)
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    for old in list(settings.get("hooks", {}).get("PreToolUse", [])):
        for handler in list(old.get("hooks", [])):
            try:
                ours = str(entry) in shlex.split(handler.get("command", ""))
            except ValueError:
                ours = False
            if ours:
                hook_unregister(settings, "PreToolUse", handler["command"])
    if args.action == "remove":
        for event in ("PermissionRequest", "PreToolUse"):
            hook_unregister(settings, event, command)
        save_json(settings_path, settings)
        # Only remove files under the installer-owned policy directory.
        if target.exists():
            shutil.rmtree(target)
        entry.unlink(missing_ok=True)
        return 0
    if target.is_symlink() or entry.is_symlink():
        raise ValueError("Policy installation paths must not be symlinks")
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target) as staging:
        staged_engine = Path(staging) / "engine"
        shutil.copytree(
            source / "engine",
            staged_engine,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        engine = target / "engine"
        if engine.is_symlink():
            engine.unlink()
        elif engine.exists():
            shutil.rmtree(engine)
        staged_engine.replace(engine)
    shutil.copy2(source / "rules.json", target / "hook-rules.json")
    shutil.copy2(source / "codex-policy.py", entry)
    matcher = "^Bash$" if getattr(args, "shell_only", False) else "^(Bash|apply_patch|mcp__.*)$"
    entries = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    desired = {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command, "timeout": 10}],
    }
    if not any(entry == desired for entry in entries):
        entries.append(desired)
    save_json(settings_path, settings)
    ok(f"Codex policy installed in {target}")
    print(f"  Decision diagnostics (no command content): {target / 'codex-events.jsonl'}")
    print("  New hook definitions require review in Codex /hooks.")
    return 0


def codex_skills(root: Path, home: Path, exclusions: set[str], dry_run: bool) -> None:
    """Compatibility entry point for the shared per-agent skill linker."""
    agent_skills(root, "codex", home, exclusions, dry_run)


def agent_skills(
    root: Path,
    agent: str,
    home: Path,
    exclusions: set[str],
    dry_run: bool,
    *,
    primary_root: Path | None = None,
) -> None:
    """Select the manifest exactly and route harness aliases through shared sources."""
    catalog = json.loads((root / "skills/compatibility.json").read_text())
    manifest_path = home / "agent-skills-links.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    skill_home = home / "skills" if agent == "claude" else Path.home() / ".agents/skills"
    canonical = Path.home() / ".agent-skills/skills"
    desired = {**catalog, "shared": {"supportedAgents": ["claude", "codex"]}}
    for name in sorted(set(desired) | set(manifest)):
        info = desired.get(name, {})
        target = skill_home / name
        source = canonical / name
        excluded = name != "shared" and ("all" in exclusions or name in exclusions)
        supported = agent in info.get("supportedAgents", [])
        ours = target.is_symlink() and (
            str(target.readlink()) in (str(source), manifest.get(name))
            or target.resolve() == (root / "skills" / name).resolve()
            or (
                primary_root is not None
                and target.resolve() == (primary_root / "skills" / name).resolve()
            )
            or target.resolve() == source.resolve()
        )
        if not supported and not excluded:
            skip(f"{name}: unavailable for {agent} — {info.get('reason', 'retired skill')}")
        if excluded or not supported:
            reason = "excluded" if excluded else "unsupported"
            if ours:
                print(f"  removed {name} ({reason})")
                if not dry_run:
                    target.unlink()
                    manifest.pop(name, None)
            elif target.exists() or target.is_symlink():
                skip(f"{name} {reason}, but {target} is not ours — left alone")
            continue
        if target.is_symlink() and target.readlink() == source:
            skip(f"{name} already linked")
            manifest[name] = str(source)
            continue
        if target.exists() or target.is_symlink():
            if not ours:
                skip(f"{target}: existing skill left alone")
                continue
        print(f"  Link {target} → {source}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            target.symlink_to(source, target_is_directory=True)
            manifest[name] = str(source)
    if not dry_run and manifest:
        save_json(manifest_path, manifest)
    elif not dry_run and manifest_path.exists():
        manifest_path.unlink()


def codex_window_titles(home: Path, dry_run: bool) -> None:
    """Retire custom Codex titles, including commands cached by running CLIs."""
    hook_dir = home / "hooks"
    path = home / "hooks.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    print("Codex: use built-in /title and /rename; retire custom title automation")
    if dry_run:
        return
    commands = (
        f"AGENT_SKILLS_HARNESS=codex bash {shlex.quote(str(hook_dir / 'window-nudge.sh'))}",
        f"python3 {shlex.quote(str(hook_dir / 'codex_terminal.py'))}",
    )
    retired_names = ("codex_terminal.py", "codex-title.py", "window-nudge.sh", "window-lib.sh")
    registered = any(
        _find_hook(entries, command) is not None
        for entries in settings.get("hooks", {}).values()
        for command in commands
    )
    if (
        not registered
        and not any((hook_dir / name).exists() for name in retired_names)
        and not (home / "scripts/window-title").exists()
    ):
        return
    for event in ("SessionStart", "UserPromptSubmit", "Stop"):
        for command in commands:
            hook_unregister(settings, event, command)
    # Old sessions retain hook commands and guidance after configuration reloads.
    # These inert stubs prevent missing-file loops without renaming anything.
    hook_dir.mkdir(parents=True, exist_ok=True)
    for name in ("codex_terminal.py", "codex-title.py"):
        (hook_dir / name).write_text("# Retired title helper: compatibility no-op.\n")
    (hook_dir / "window-nudge.sh").write_text("#!/bin/sh\n# Retired title nudge.\nexit 0\n")
    (hook_dir / "window-lib.sh").unlink(missing_ok=True)
    script = home / "scripts/window-title"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'Automatic Codex title changes are retired; use /rename in the CLI.'\n"
    )
    script.chmod(0o755)
    save_json(path, settings)


def guidance_content(root: Path, target: str, user: str | None = None) -> str:
    """Concatenate maintained common, harness and optional personal text."""
    paths = [root / "templates/user-agents-guidance.md", root / f"templates/user-{target}.md"]
    if user:
        if Path(user).name != user or user in (".", ".."):
            raise ValueError("User template must be a name, not a path")
        personal = root / "templates" / f"{user}.md"
        if personal.exists():
            paths.append(personal)
    return "\n\n".join(p.read_text().strip() for p in paths) + "\n"


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
        content = (
            args.content_text if hasattr(args, "content_text") else _read_content(args.content)
        )
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

    p = sub.add_parser("codex-policy")
    p.add_argument("action", choices=["install", "remove"])
    p.add_argument("codex_home")
    p.add_argument("source")
    p.add_argument("--shell-only", action="store_true")

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
    "codex-policy": cmd_codex_policy,
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
