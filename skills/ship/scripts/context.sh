#!/bin/bash
# Pre-loaded context helper for ship skill.
# Usage: context.sh <flag>
case "$1" in
  pr-template)
    if [ -f .github/pull_request_template.md ]; then echo "found"; else echo "none"; fi
    ;;
  unpushed)
    git log --oneline "@{u}.." 2>/dev/null | head -10
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
