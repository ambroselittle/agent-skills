#!/usr/bin/env bash
# Sets up agent skills: links skills into ~/.claude/skills/, installs hook rules,
# merges settings.json permissions, and upserts CLAUDE.md guidance.
# Run after cloning or adding new skills.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CLAUDE_SKILLS_DIR="$CLAUDE_DIR/skills"
CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
HOOKS_DIR="$CLAUDE_DIR/hooks"

mkdir -p "$CLAUDE_SKILLS_DIR"

# --------------------------------------------------------------------------- #
# 1. Link skills                                                              #
# --------------------------------------------------------------------------- #

echo "Linking skills from $SCRIPT_DIR/skills/..."
for skill_dir in "$SCRIPT_DIR"/skills/*/; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"

  # Skip non-skill directories (no SKILL.md) — shared/ is handled separately
  [[ -f "$skill_dir/SKILL.md" ]] || continue

  target="$CLAUDE_SKILLS_DIR/$skill_name"

  if [[ -L "$target" ]]; then
    existing="$(readlink "$target")"
    if [[ "$existing" == "$skill_dir" || "$existing" == "${skill_dir%/}" ]]; then
      echo "  $skill_name: already linked"
      continue
    else
      echo "  $skill_name: WARNING - symlink exists pointing to $existing, skipping"
      continue
    fi
  elif [[ -e "$target" ]]; then
    echo "  $skill_name: WARNING - non-symlink exists at $target, skipping"
    continue
  fi

  ln -s "${skill_dir%/}" "$target"
  echo "  $skill_name: linked"
done

# Link shared resources (agents, scripts used by multiple skills)
shared_source="$SCRIPT_DIR/skills/shared"
shared_target="$CLAUDE_SKILLS_DIR/shared"

if [[ -d "$shared_source" ]]; then
  if [[ -L "$shared_target" ]]; then
    existing="$(readlink "$shared_target")"
    if [[ "$existing" == "$shared_source" ]]; then
      echo "  shared: already linked"
    else
      echo "  shared: WARNING - symlink exists pointing to $existing, skipping"
    fi
  elif [[ -e "$shared_target" ]]; then
    echo "  shared: WARNING - non-symlink exists at $shared_target, skipping"
  else
    ln -s "$shared_source" "$shared_target"
    echo "  shared: linked"
  fi
fi

# --------------------------------------------------------------------------- #
# 2. Install PreToolUse hook rules                                            #
# --------------------------------------------------------------------------- #

echo ""
echo "Installing PreToolUse hook rules..."

hook_source="$SCRIPT_DIR/hooks/PreToolUse/rules.json"
hook_target_dir="$HOOKS_DIR/pre-tool-use"
hook_target="$hook_target_dir/hook-rules.json"

if [[ -f "$hook_source" ]]; then
  mkdir -p "$hook_target_dir"

  # Always overwrite the engine with repo version
  if [[ -d "$SCRIPT_DIR/hooks/PreToolUse/engine" ]]; then
    # Remove legacy src/ directory if present
    [[ -d "$hook_target_dir/src" ]] && rm -rf "$hook_target_dir/src"
    rm -rf "$hook_target_dir/engine"
    cp -r "$SCRIPT_DIR/hooks/PreToolUse/engine" "$hook_target_dir/engine"
    echo "  Installed hook engine to $hook_target_dir/engine"
  fi

  # Install the entry point script
  if [[ -f "$SCRIPT_DIR/hooks/PreToolUse/pre-tool-use.sh" ]]; then
    cp "$SCRIPT_DIR/hooks/PreToolUse/pre-tool-use.sh" "$HOOKS_DIR/pre-tool-use.sh"
    chmod +x "$HOOKS_DIR/pre-tool-use.sh"
    echo "  Installed hook entry point to $HOOKS_DIR/pre-tool-use.sh"
  fi

  # Always overwrite rules with repo version
  cp "$hook_source" "$hook_target"
  echo "  Installed hook rules to $hook_target"
else
  echo "  WARNING: $hook_source not found, skipping hook rules"
fi

# --------------------------------------------------------------------------- #
# 3. Merge built-in rules into settings.json permissions                      #
# --------------------------------------------------------------------------- #

echo ""
echo "Merging permissions into settings.json..."

builtin_rules="$SCRIPT_DIR/hooks/PreToolUse/built-in-rules.json"

if [[ -f "$builtin_rules" ]]; then
  # Use Python for reliable JSON merging
  python3 - "$CLAUDE_SETTINGS" "$builtin_rules" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]
rules_path = sys.argv[2]

# Load or create settings
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

# Load built-in rules
with open(rules_path) as f:
    rules = json.load(f)

# Ensure permissions structure exists
if "permissions" not in settings:
    settings["permissions"] = {}

# Merge allow rules — union of existing and repo-managed
existing_allow = set(settings["permissions"].get("allow", []))
repo_allow = set(rules.get("allow", []))
settings["permissions"]["allow"] = sorted(existing_allow | repo_allow)

# Merge deny rules — union of existing and repo-managed
existing_deny = set(settings["permissions"].get("deny", []))
repo_deny = set(rules.get("deny", []))
settings["permissions"]["deny"] = sorted(existing_deny | repo_deny)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  Merged {len(repo_allow)} allow and {len(repo_deny)} deny rules into {settings_path}")
PYEOF
else
  echo "  WARNING: $builtin_rules not found, skipping permissions merge"
fi

# --------------------------------------------------------------------------- #
# 4. Upsert <agent-skills-guidance> block in CLAUDE.md                        #
# --------------------------------------------------------------------------- #

echo ""
echo "Updating CLAUDE.md guidance..."

core_template="$SCRIPT_DIR/templates/user-claude.md"

if [[ -f "$core_template" ]]; then
  # Determine GitHub username for personal template lookup
  gh_user=""
  if command -v gh &>/dev/null; then
    gh_user="$(gh api user --jq .login 2>/dev/null || true)"
  fi

  # Build the fenced block content: core + optional personal
  block_content="$(cat "$core_template")"

  if [[ -n "$gh_user" ]] && [[ -f "$SCRIPT_DIR/templates/${gh_user}.md" ]]; then
    block_content="${block_content}

$(cat "$SCRIPT_DIR/templates/${gh_user}.md")"
    echo "  Including personal template for $gh_user"
  fi

  # Upsert the fenced block in CLAUDE.md
  python3 - "$CLAUDE_MD" "$block_content" <<'PYEOF'
import sys
from pathlib import Path

claude_md_path = sys.argv[1]
new_content = sys.argv[2]

open_tag = "<agent-skills-guidance>"
close_tag = "</agent-skills-guidance>"

fenced_block = f"{open_tag}\n{new_content}\n{close_tag}"

claude_md = Path(claude_md_path)

if claude_md.exists():
    existing = claude_md.read_text()

    if open_tag in existing and close_tag in existing:
        # Replace existing block
        before = existing[:existing.index(open_tag)]
        after = existing[existing.index(close_tag) + len(close_tag):]
        updated = before + fenced_block + after
        action = "Updated"
    elif open_tag in existing or close_tag in existing:
        # Malformed — one tag without the other. Warn and prepend.
        print("  WARNING: Found orphaned agent-skills-guidance tag — prepending fresh block")
        updated = fenced_block + "\n\n" + existing
        action = "Prepended (orphaned tag found)"
    else:
        # No block yet — prepend
        updated = fenced_block + "\n\n" + existing
        action = "Prepended"
else:
    updated = fenced_block + "\n"
    action = "Created"

claude_md.write_text(updated)
print(f"  {action} agent-skills-guidance block in {claude_md_path}")
PYEOF
else
  echo "  WARNING: $core_template not found, skipping CLAUDE.md update"
fi

echo ""
echo "Done."
