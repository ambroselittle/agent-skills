#!/bin/bash
# Writes a single correction-capture file to ~/.agent-skills/wtf/
# and prints the absolute file path on stdout.
#
# Usage: capture.sh <message...>
#
# Environment:
#   CLAUDE_SESSION_ID: optional; included in frontmatter when set.
#
# Exits non-zero only when no message is provided. All other failures
# (git commands, transcript extraction) degrade gracefully.

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: capture.sh <message>" >&2
  exit 1
fi

message="$*"
script_dir="$(cd "$(dirname "$0")" && pwd)"

# Timestamps — filename uses a compact sortable form, frontmatter uses full ISO 8601.
ts_file=$(date -u +%Y%m%dT%H%M%SZ)
ts_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Slug from the message: lowercase, non-alnum collapsed to -, trimmed, max 40 chars.
slug=$(printf '%s' "$message" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-//; s/-$//' \
  | cut -c1-40 \
  | sed -E 's/-$//')
slug=${slug:-untitled}

# Context — fall back gracefully if we're not in a git repo or git is unavailable.
cwd="${PWD:-$(pwd)}"
session_id="${CLAUDE_SESSION_ID:-unknown}"
branch=$(git -C "$cwd" branch --show-current 2>/dev/null || echo "no-branch")

# Pull the conversation tail from the transcript (degrades gracefully).
turns=$("$script_dir/extract-turns.sh" "$cwd" 2>/dev/null || echo "(transcript unavailable)")

# Destination directory — permissive on ~/.agent-skills/ per built-in-rules.
dir="$HOME/.agent-skills/wtf"
mkdir -p "$dir"

# Atomic write: temp file in the same directory, then rename.
tmpfile=$(mktemp "$dir/.tmp-XXXXXXXX")
trap 'rm -f "$tmpfile"' EXIT

cat > "$tmpfile" << EOF
---
timestamp: $ts_iso
session_id: $session_id
cwd: $cwd
branch: $branch
---

# $slug

## User said

$message

## Context

- **Branch:** \`$branch\`
- **Session:** \`$session_id\`
- **Cwd:** \`$cwd\`

## Transcript

$turns

## My take

<!-- Optional. The worker classifier will determine the right action regardless. -->
EOF

outfile="$dir/${ts_file}-${slug}.md"
mv "$tmpfile" "$outfile"
trap - EXIT

echo "$outfile"
