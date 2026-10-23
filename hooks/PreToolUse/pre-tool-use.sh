#!/usr/bin/env bash
# Pre-tool-use hook entry point.
#
# Registered in ~/.claude/settings.json hooks.PreToolUse.
# Receives tool call JSON on stdin, outputs a JSON decision to stdout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Engine lives in a sibling directory named after the hook (pre-tool-use/)
INTERPRETER="$SCRIPT_DIR/pre-tool-use/engine/interpreter.py"

if [ ! -f "$INTERPRETER" ]; then
    echo "Pre-tool-use rules engine not found." >&2
    exit 0
fi

# Use the runtime selected at setup, even when an older python3 leads PATH.
PYTHON="$HOME/.agent-skills/scripts/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "Agent Skills Python runtime is unavailable; reapply setup with Python 3.12+." >&2
    exit 0
fi

if OUTPUT="$("$PYTHON" "$INTERPRETER")"; then
    printf '%s\n' "$OUTPUT"
else
    echo "Pre-tool-use rules engine failed. Claude Code's built-in rules are now in effect." >&2
fi
exit 0
