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

# Check python3 3.9+ availability (once per boot, cached via temp file)
PYTHON_CHECK="/tmp/.agent-skills-python-ok"
if [ ! -f "$PYTHON_CHECK" ]; then
    if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        echo "Hook engine requires python3 3.9+. Install via: xcode-select --install" >&2
        exit 0
    fi
    touch "$PYTHON_CHECK"
fi

INPUT="$(cat)"

if OUTPUT="$(echo "$INPUT" | python3 "$INTERPRETER" 2> >(tee /tmp/hook-error.txt >&2))"; then
    echo "$OUTPUT"
else
    ERROR_MSG="$(cat /tmp/hook-error.txt 2>/dev/null | head -3 | tr '\n' ' ')"
    echo "Pre-tool-use rules engine failed${ERROR_MSG:+ — }${ERROR_MSG}. Claude Code's built-in rules are now in effect." >&2
fi
exit 0
