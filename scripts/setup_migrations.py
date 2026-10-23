"""Versioned installer upgrades; original user configuration is never removed."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

import setup_config


def merge_preserving_overrides(base: dict, overrides: dict) -> dict:
    """Merge objects recursively, retaining unknown values and explicit overrides."""
    result = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_preserving_overrides(result[key], value)
        else:
            result[key] = value
    return result


def import_legacy_config() -> None:
    """Version zero kept base preferences in Claude and overrides in Codex."""
    path = setup_config.config_path()
    legacy = setup_config.load_json(Path.home() / ".claude/agent-skills.json")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    codex = setup_config.load_json(codex_home / "agent-skills.json")
    if codex:
        agents = legacy.get("agents")
        if not isinstance(agents, dict):
            agents = {}
        legacy = {**legacy, "agents": {**agents, "codex": codex}}
    merged = merge_preserving_overrides(legacy, setup_config.load_json(path))
    if merged or not path.exists():
        setup_config.save_json(path, merged)


def remove_owned_approval_hooks(codex_home: Path) -> None:
    """Retire our old approval decisions, preserving unrelated hooks and metadata."""
    path = codex_home / "hooks.json"
    if not path.exists():
        return
    # Corrupt user hook configuration must remain intact for the user to repair.
    import json

    settings = json.loads(path.read_text())
    hooks = settings.get("hooks", {})
    entries = hooks.get("PermissionRequest", [])
    owned = str(codex_home / "hooks/agent-skills-permission-request.py")
    changed = False
    kept = []
    for entry in entries:
        handlers = []
        for handler in entry.get("hooks", []):
            try:
                ours = owned in shlex.split(handler.get("command", ""))
            except ValueError:
                ours = False
            if ours:
                changed = True
            else:
                handlers.append(handler)
        if handlers:
            kept.append({**entry, "hooks": handlers})
    if not changed:
        return
    if kept:
        hooks["PermissionRequest"] = kept
    else:
        hooks.pop("PermissionRequest", None)
    if not hooks:
        settings.pop("hooks", None)
    setup_config.save_json(path, settings)


def shared_install_v1(state: dict) -> None:
    if not os.environ.get("AGENT_SKILLS_CONFIG"):
        import_legacy_config()
        state["legacy_config_imported"] = True
    else:
        # An explicit config opts out of import without consuming the later
        # default-config migration on the same machine.
        state["legacy_config_imported"] = False
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    remove_owned_approval_hooks(home)


MIGRATIONS = ((1, shared_install_v1),)
CURRENT_VERSION = MIGRATIONS[-1][0]


def migrate() -> None:
    """Run ordered upgrades once; preserve unknown state keys across versions."""
    path = Path.home() / ".agent-skills/state.json"
    state = setup_config.load_json(path)
    version = state.get("version", 0)
    if not isinstance(version, int) or version < 0 or version > CURRENT_VERSION:
        raise ValueError("Unsupported agent-skills state version")
    changed = False
    for next_version, upgrade in MIGRATIONS:
        if version < next_version:
            upgrade(state)
            state["version"] = next_version
            changed = True
    if not os.environ.get("AGENT_SKILLS_CONFIG") and state.get("legacy_config_imported") is False:
        import_legacy_config()
        state["legacy_config_imported"] = True
        changed = True
    if changed:
        setup_config.save_json(path, state)
