#!/usr/bin/env bash
# Restore a skill's symlink to the main repo after dev-skill.sh.
# Usage: ./undev-skill.sh <skill-name> [skill-name ...]
#        ./undev-skill.sh --all

set -euo pipefail

CLAUDE_SKILLS_DIR="$HOME/.claude/skills"

if [[ $# -eq 0 ]]; then
  echo "Usage: undev-skill.sh <skill-name> [skill-name ...]"
  echo "       undev-skill.sh --all"
  echo ""
  echo "Currently dev-linked:"
  found=0
  for backup in "$CLAUDE_SKILLS_DIR"/*.main-repo; do
    [[ -f "$backup" ]] || continue
    skill="$(basename "${backup%.main-repo}")"
    original="$(cat "$backup")"
    echo "  $skill → $(readlink "$CLAUDE_SKILLS_DIR/$skill") (was $original)"
    found=1
  done
  [[ $found -eq 0 ]] && echo "  (none)"
  exit 1
fi

# Expand --all to all dev-linked skills
if [[ "$1" == "--all" ]]; then
  skills=()
  for backup in "$CLAUDE_SKILLS_DIR"/*.main-repo; do
    [[ -f "$backup" ]] || continue
    skill="$(basename "${backup%.main-repo}")"
    skills+=("$skill")
  done
  if [[ ${#skills[@]} -eq 0 ]]; then
    echo "No dev-linked skills to restore."
    exit 0
  fi
  set -- "${skills[@]}"
fi

for skill in "$@"; do
  target="$CLAUDE_SKILLS_DIR/$skill"
  backup="$target.main-repo"

  if [[ ! -f "$backup" ]]; then
    echo "  $skill: no backup found (wasn't dev-linked?), skipping"
    continue
  fi

  original="$(cat "$backup")"
  rm -f "$target"
  ln -s "$original" "$target"
  rm "$backup"
  echo "  $skill: restored → $original"
done
