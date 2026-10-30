#!/usr/bin/env bash
# Explicit workflow context; callable from Claude Code or Codex.
set -euo pipefail

script_dir="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="$HOME/.agent-skills/scripts/python"
if [[ ! -x "$python" ]]; then
  if [[ -e "$HOME/.agent-skills/source" ]]; then
    echo "Missing selected Python: $python. Reapply agent-skills setup." >&2
    exit 1
  fi
  python="$(command -v python3)"
fi
"$python" "$script_dir/../../shared/scripts/workflow_context.py" shared "$@"
