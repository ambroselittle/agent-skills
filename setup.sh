#!/usr/bin/env bash
# Links agent skills from personal and employer repos into ~/.claude/skills/
# Run after cloning repos or adding new skills.

set -euo pipefail

CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
PERSONAL_DIR="$HOME/Repos/ambroselittle/agent-skills"
EMPLOYER_DIR="$HOME/Repos/mcd/agent-skills"

mkdir -p "$CLAUDE_SKILLS_DIR"

link_skills() {
  local source_dir="$1"
  local label="$2"

  if [[ ! -d "$source_dir" ]]; then
    echo "Skipping $label: $source_dir not found"
    return
  fi

  for skill_dir in "$source_dir"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"

    # Skip non-skill directories (no SKILL.md)
    [[ -f "$skill_dir/SKILL.md" ]] || continue

    target="$CLAUDE_SKILLS_DIR/$skill_name"

    if [[ -L "$target" ]]; then
      existing="$(readlink "$target")"
      if [[ "$existing" == "$skill_dir" || "$existing" == "${skill_dir%/}" ]]; then
        echo "  $skill_name: already linked ($label)"
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
    echo "  $skill_name: linked ($label)"
  done
}

echo "Linking personal skills..."
link_skills "$PERSONAL_DIR" "personal"

echo "Linking employer skills..."
link_skills "$EMPLOYER_DIR" "employer"

echo "Done."
