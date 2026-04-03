#!/usr/bin/env bash
# Links agent skills and shared resources into ~/.claude/skills/
# Run after cloning or adding new skills.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"

mkdir -p "$CLAUDE_SKILLS_DIR"

# Link individual skills (directories containing SKILL.md)
echo "Linking skills from $SCRIPT_DIR..."
for skill_dir in "$SCRIPT_DIR"/*/; do
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
shared_source="$SCRIPT_DIR/shared"
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

echo "Done."
