"""Versioned installer upgrades; original user configuration is never removed."""

from __future__ import annotations

import json
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


def shared_install_v1(state: dict, _root: Path, _primary_root: Path) -> None:
    if not os.environ.get("AGENT_SKILLS_CONFIG"):
        import_legacy_config()
        state["legacy_config_imported"] = True
    else:
        # An explicit config opts out of import without consuming the later
        # default-config migration on the same machine.
        state["legacy_config_imported"] = False
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    remove_owned_approval_hooks(home)


def reconcile_retired_skills(_state: dict, root: Path, primary_root: Path) -> None:
    """Remove obsolete owned aliases without touching source or foreign installs."""
    catalog = json.loads((root / "skills/compatibility.json").read_text())
    if not isinstance(catalog, dict):
        raise ValueError("Skill compatibility catalog must be an object")
    active = set(catalog) | {"shared", "python"}
    shared = Path.home() / ".agent-skills"
    codex = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    locations = (
        (Path.home() / ".claude/skills", Path.home() / ".claude/agent-skills-links.json"),
        (Path.home() / ".agents/skills", codex / "agent-skills-links.json"),
    )

    def valid_name(name: str) -> bool:
        return name not in active and name not in ("", ".", "..") and Path(name).name == name

    def owned_link(path: Path, sources: tuple[Path, ...], recorded: object = None) -> bool:
        if not path.is_symlink():
            return False
        raw = str(path.readlink())
        resolved = str(path.resolve())
        return (isinstance(recorded, str) and recorded in (raw, resolved)) or any(
            path.resolve() == source.resolve() for source in sources
        )

    for skill_home, manifest_path in locations:
        manifest = setup_config.load_json(manifest_path)
        candidates = set(manifest)
        if skill_home.is_dir():
            candidates.update(path.name for path in skill_home.iterdir())
        changed = False
        for name in candidates:
            if not valid_name(name):
                continue
            link = skill_home / name
            expected = (
                root / "skills" / name,
                primary_root / "skills" / name,
                shared / "skills" / name,
            )
            record = manifest.get(name)
            ours = owned_link(link, expected, record)
            if ours:
                link.unlink()
                setup_config.ok(f"Removed retired owned skill link: {link}")
            # Unknown metadata is not a skill ownership record. Keep it even
            # when its key happens to look like a removed skill's name.
            known_record = isinstance(record, str) and any(record == str(path) for path in expected)
            if name in manifest and (ours or known_record):
                del manifest[name]
                changed = True
        if changed:
            if manifest:
                setup_config.save_json(manifest_path, manifest)
            else:
                manifest_path.unlink()

    resources_path = shared / "resource-links.json"
    resources = setup_config.load_json(resources_path)
    candidates = set()
    for kind in ("skills", "scripts"):
        directory = shared / kind
        if directory.is_dir():
            candidates.update(path.name for path in directory.iterdir())
    for key, value in resources.items():
        parts = Path(key).parts
        if len(parts) == 2 and parts[0] in ("skills", "scripts") and isinstance(value, str):
            candidates.add(parts[1])
    changed = False
    for name in candidates:
        if not valid_name(name):
            continue
        for kind in ("skills", "scripts"):
            key = f"{kind}/{name}"
            link = shared / key
            suffix = (name,) if kind == "skills" else (name, "scripts")
            sources = (root.joinpath("skills", *suffix), primary_root.joinpath("skills", *suffix))
            record = resources.get(key)
            ours = owned_link(link, sources, record)
            if ours:
                link.unlink()
                setup_config.ok(f"Removed retired owned resource alias: {link}")
            known_record = isinstance(record, str) and any(record == str(path) for path in sources)
            if key in resources and (ours or known_record):
                del resources[key]
                changed = True
    if changed:
        setup_config.save_json(resources_path, resources)


MIGRATIONS = ((1, shared_install_v1), (2, reconcile_retired_skills))
CURRENT_VERSION = MIGRATIONS[-1][0]


def migrate(root: Path | None = None, primary_root: Path | None = None) -> None:
    """Run ordered upgrades once; preserve unknown state keys across versions."""
    path = Path.home() / ".agent-skills/state.json"
    root = root or Path(__file__).resolve().parents[1]
    primary_root = primary_root or root
    state = setup_config.load_json(path)
    version = state.get("version", 0)
    if not isinstance(version, int) or version < 0 or version > CURRENT_VERSION:
        raise ValueError("Unsupported agent-skills state version")
    changed = False
    for next_version, upgrade in MIGRATIONS:
        if version < next_version:
            upgrade(state, root, primary_root)
            state["version"] = next_version
            changed = True
    if not os.environ.get("AGENT_SKILLS_CONFIG") and state.get("legacy_config_imported") is False:
        import_legacy_config()
        state["legacy_config_imported"] = True
        changed = True
    if changed:
        setup_config.save_json(path, state)
