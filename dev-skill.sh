#!/usr/bin/env bash
# Temporarily repoint a skill's symlink to the current worktree.
# Usage: ./dev-skill.sh <skill-name> [skill-name ...]
#
# When developing a skill in a git worktree, ~/.claude/skills/<skill> points
# to the main repo where your changes don't exist yet. This script swaps the
# symlink to point at the worktree so you can test interactively.
#
# Run `./restore-skill.sh <skill-name>` to restore the original symlink,
# or re-run `./setup.sh` from the main repo to reset all skills.

set -euo pipefail

CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_REPO="$(git -C "$REPO_ROOT" rev-parse --git-common-dir 2>/dev/null | sed 's|/\.git$||')"

if [[ $# -eq 0 ]]; then
  echo "Usage: dev-skill.sh <skill-name> [skill-name ...]"
  echo ""
  echo "Available skills in this worktree:"
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] && echo "  $(basename "$d")"
  done
  exit 1
fi

for skill in "$@"; do
  skill_dir="$REPO_ROOT/skills/$skill"
  target="$CLAUDE_SKILLS_DIR/$skill"
  backup="$target.main-repo"

  if [[ ! -d "$skill_dir" ]] || [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "  $skill: not found in this worktree (no SKILL.md), skipping"
    continue
  fi

  # Already pointing at this worktree?
  if [[ -L "$target" ]] && [[ "$(readlink "$target")" == "$skill_dir" ]]; then
    echo "  $skill: already dev-linked to this worktree"
    continue
  fi

  # Save the original symlink for undev-skill.sh to restore
  if [[ -L "$target" ]] && [[ ! -e "$backup" ]]; then
    original="$(readlink "$target")"
    echo "$original" > "$backup"
  fi

  # Swap the symlink
  rm -f "$target"
  ln -s "$skill_dir" "$target"
  echo "  $skill: dev-linked → $skill_dir"
done
