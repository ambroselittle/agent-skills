#!/bin/bash
# Pre-loaded context helper for plan-review skill.
# Usage: context.sh <flag>
case "$1" in
  plan-reviewer-agents)
    # Merge repo agents + built-in agents into a single pool.
    # Repo agents override built-ins of the same name.
    # Agents with `always: true` frontmatter are always included; others are coordinator-selectable.
    _skill_dir="$(cd "$(dirname "$0")/.." && pwd)"
    _builtin_dir="$_skill_dir/agents"
    _repo_dir=".claude/agents/plan-reviewers"

    _all_names=$(
      { ls "$_builtin_dir"/*.md 2>/dev/null; ls "$_repo_dir"/*.md 2>/dev/null; } \
        | xargs -I{} basename {} .md | sort -u
    )

    _always="" _selectable=""
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if   [[ -f "$_repo_dir/$name.md" ]];    then f="$_repo_dir/$name.md"
      elif [[ -f "$_builtin_dir/$name.md" ]]; then f="$_builtin_dir/$name.md"
      else continue; fi
      if grep -q "^always: true" "$f" 2>/dev/null; then
        _always="$_always $name"
      else
        _selectable="$_selectable $name"
      fi
    done <<< "$_all_names"

    printf "always-on: %s\n"   "$(echo $_always    | xargs)"
    printf "selectable: %s\n"  "$(echo $_selectable | xargs)"
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
