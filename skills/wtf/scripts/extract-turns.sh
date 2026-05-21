#!/bin/bash
# Extracts the last ~10 user/assistant turns from the Claude Code transcript
# for the current session. Degrades gracefully if anything is missing.
#
# Usage: extract-turns.sh [cwd]
#   cwd: optional; defaults to $PWD. Used to compute the Claude project slug.
#
# Environment:
#   CLAUDE_SESSION_ID: required. The session ID injected by Claude Code.
#
# Output: markdown to stdout. On any failure, prints a "(transcript unavailable: ...)"
# line and exits 0 so the caller never fails because of this helper.

set -euo pipefail

cwd="${1:-${PWD:-$(pwd)}}"
session_id="${CLAUDE_SESSION_ID:-}"

if [ -z "$session_id" ]; then
  echo "(transcript unavailable: CLAUDE_SESSION_ID not set)"
  exit 0
fi

# Claude Code project slug: replace / and . with - in the absolute path.
slug=$(printf '%s' "$cwd" | tr '/.' '--')
transcript="$HOME/.claude/projects/${slug}/${session_id}.jsonl"

if [ ! -f "$transcript" ]; then
  echo "(transcript unavailable: $transcript not found)"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "(transcript unavailable: jq not installed)"
  exit 0
fi

# Pull last ~100 lines, keep only user/assistant turns, take the last 10,
# then render each as markdown with a truncated content preview (~800 chars).
tail -n 100 "$transcript" \
  | jq -c 'select(.type == "user" or .type == "assistant") | select(.message.role == "user" or .message.role == "assistant")' 2>/dev/null \
  | tail -n 10 \
  | jq -r '
      (.message.role | ascii_upcase) as $role |
      (
        if (.message.content | type) == "string" then
          .message.content
        else
          (.message.content | map(
            if .type == "text" then .text
            elif .type == "tool_use" then "[tool-use: \(.name // "?")]"
            elif .type == "tool_result" then "[tool-result]"
            else ""
            end
          ) | join("\n"))
        end
      ) as $content |
      "### \($role)\n\n\($content | .[0:800])"
    ' 2>/dev/null \
  || echo "(transcript unavailable: parse error)"
