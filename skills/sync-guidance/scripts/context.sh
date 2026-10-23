#!/bin/bash
# Explicit context loading for both Claude Code and Codex.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
python="$HOME/.agent-skills/scripts/python"
if [ ! -x "$python" ]; then
  python=python3
fi
"$python" "$script_dir/context.py" "$@"
