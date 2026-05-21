#!/bin/bash
# Appends a correction to the rolling WTF backlog issue in ambroselittle/agent-skills,
# or creates a new issue if none is currently open-and-unclaimed.
#
# Usage: backlog-append.sh <correction-file-path>
#
# Intended to be run detached (nohup ... & disown) by the /wtf skill so the
# skill returns immediately. Logs to stderr; prints the issue URL to stdout
# on success.

set -euo pipefail

file="${1:-}"
if [ -z "$file" ] || [ ! -f "$file" ]; then
  echo "Usage: backlog-append.sh <correction-file-path>" >&2
  exit 1
fi

REPO="ambroselittle/agent-skills"
TITLE="WTF backlog"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found — skipping backlog append" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh not authenticated — skipping backlog append" >&2
  exit 1
fi

# Ensure both labels exist on the repo. `--force` creates-or-updates, so this is
# idempotent and safe on every invocation. Cheap bootstrap so the capture skill
# works standalone without requiring `setup.sh --install-wtf-worker` first.
gh label create WTF -R "$REPO" --color FF6347 \
  --description "Correction captured via /wtf skill" --force >/dev/null 2>&1 || true
gh label create "In Progress" -R "$REPO" --color FBCA04 \
  --description "Active claim by an autonomous worker" --force >/dev/null 2>&1 || true

# Strip YAML frontmatter (first ---...--- block) so the entry renders cleanly in GH.
entry=$(awk '
  /^---$/ {
    if (!seen_open) { seen_open = 1; next }
    if (!seen_close) { seen_close = 1; next }
  }
  seen_open && !seen_close { next }
  seen_close { print }
' "$file")

marker="<!-- entry: $(basename "$file") -->"
new_entry="${marker}

${entry}"

# Query: any open issue labeled WTF that isn't currently In Progress.
existing=$(gh issue list \
  -R "$REPO" \
  --state open \
  --label WTF \
  --search '-label:"In Progress"' \
  --json number,body,url \
  --limit 1)

count=$(printf '%s' "$existing" | jq 'length')

if [ "$count" -gt 0 ]; then
  num=$(printf '%s' "$existing" | jq -r '.[0].number')
  url=$(printf '%s' "$existing" | jq -r '.[0].url')
  existing_body=$(printf '%s' "$existing" | jq -r '.[0].body')
  new_body="${existing_body}

---

${new_entry}"
  gh issue edit "$num" -R "$REPO" --body "$new_body" >/dev/null
  echo "Appended correction to $url" >&2
  echo "$url"
else
  url=$(gh issue create \
    -R "$REPO" \
    --title "$TITLE" \
    --label WTF \
    --body "$new_entry")
  echo "Created new backlog issue: $url" >&2
  echo "$url"
fi
