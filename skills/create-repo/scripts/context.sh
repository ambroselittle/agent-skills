#!/bin/bash
# Pre-loaded context helper for create-repo skill.
# Usage: context.sh <flag>
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"

case "$1" in
  repo-home)
    cd "$SKILL_DIR" && uv run python -m scripts.find_repo_home 2>/dev/null || echo '{}'
    ;;
  list-templates)
    cd "$SKILL_DIR" && uv run python -m scripts.list_templates 2>/dev/null || echo '(templates unavailable)'
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
