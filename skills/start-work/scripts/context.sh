#!/bin/bash
# Pre-loaded context helper for start-work skill.
# Usage: context.sh <flag>
case "$1" in
  claude-md-exists)
    if [ -f CLAUDE.md ]; then echo "yes"; else echo "no"; fi
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
