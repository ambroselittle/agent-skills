#!/bin/bash
# Autonomous worker for the /wtf correction backlog.
#
# Runs on a launchd schedule. Looks for actionable work:
#   1) A WTF-labeled open issue without an "In Progress" label → new-work mode
#   2) A WTF-labeled open PR in CHANGES_REQUESTED review state without
#      "In Progress" → iterate mode
#
# When it finds work, it claims the item by adding "In Progress",
# shallow-clones ambroselittle/agent-skills to /tmp/, and hands off to
# `claude -p` with scripts/wtf-worker-prompt.md prepended to an invocation
# header describing the work item. The Claude session does the actual
# classification, edits, tests, push, and PR creation/update.
#
# Usage: wtf-worker.sh [--dry-run]
#
# --dry-run: find work and print the planned action without claiming,
#            cloning, or invoking Claude. Useful for smoke-testing and
#            launchd verification.

set -euo pipefail

REPO="ambroselittle/agent-skills"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/wtf-worker.log"
LOCK_DIR="$HOME/.agent-skills/.wtf-worker.lock.d"
STALE_LOCK_MINUTES=60
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/wtf-worker-prompt.md"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --help|-h)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$LOG_DIR" "$HOME/.agent-skills"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE" >&2
}

# Lockdir acquisition with stale cleanup. `mkdir` is atomic on POSIX — if
# two workers race, only one succeeds. If an old lockdir exceeds the stale
# threshold, we reclaim it (previous worker presumably died).
if [ -d "$LOCK_DIR" ]; then
  if find "$LOCK_DIR" -maxdepth 0 -mmin +$STALE_LOCK_MINUTES 2>/dev/null | read -r; then
    log "stale lockdir detected (>${STALE_LOCK_MINUTES}min), reclaiming"
    rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
  else
    log "lockdir held by another worker, exiting"
    exit 0
  fi
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "failed to acquire lockdir (race with another worker), exiting"
  exit 0
fi

# Cleanup trap: clear the lockdir, nuke the clone, and drop the claim if
# the worker exits abnormally while holding a work item.
CLONE_DIR=""
WORK_TYPE=""
WORK_NUM=""
CLAIMED=0

cleanup() {
  local rc=$?
  if [ -n "$CLONE_DIR" ] && [ -d "$CLONE_DIR" ]; then
    rm -rf "$CLONE_DIR"
  fi
  rmdir "$LOCK_DIR" 2>/dev/null || true
  if [ "$rc" -ne 0 ] && [ "$CLAIMED" -eq 1 ]; then
    log "worker failed (rc=$rc), dropping claim on $WORK_TYPE #$WORK_NUM"
    gh "$WORK_TYPE" edit "$WORK_NUM" -R "$REPO" --remove-label "In Progress" \
      >/dev/null 2>&1 || true
    local tail_log
    tail_log=$(tail -20 "$LOG_FILE" 2>/dev/null | sed 's/`/\\`/g')
    gh "$WORK_TYPE" comment "$WORK_NUM" -R "$REPO" \
      --body "Worker failed (rc=$rc). Tail of log:

\`\`\`
$tail_log
\`\`\`" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# 3-attempt retry for transient gh failures. Increasing backoff.
gh_retry() {
  local max=3
  local attempt=1
  while true; do
    if "$@"; then return 0; fi
    if [ "$attempt" -ge "$max" ]; then return 1; fi
    log "gh call failed, retry $attempt/$max"
    sleep $((attempt * 2))
    attempt=$((attempt + 1))
  done
}

log "worker starting (dry-run=$DRY_RUN)"

# ----- Phase 1: find work -----

MODE=""
work_url=""
work_body=""
work_head=""

new_work=$(gh_retry gh issue list \
  -R "$REPO" \
  --state open \
  --label WTF \
  --search '-label:"In Progress"' \
  --json number,url,body \
  --limit 1)

if [ "$(printf '%s' "$new_work" | jq 'length')" -gt 0 ]; then
  WORK_TYPE="issue"
  WORK_NUM=$(printf '%s' "$new_work" | jq -r '.[0].number')
  work_url=$(printf '%s' "$new_work" | jq -r '.[0].url')
  work_body=$(printf '%s' "$new_work" | jq -r '.[0].body')
  MODE="new"
else
  iter_work=$(gh_retry gh pr list \
    -R "$REPO" \
    --state open \
    --label WTF \
    --search 'review:changes-requested -label:"In Progress"' \
    --json number,url,body,headRefName \
    --limit 1)

  if [ "$(printf '%s' "$iter_work" | jq 'length')" -gt 0 ]; then
    WORK_TYPE="pr"
    WORK_NUM=$(printf '%s' "$iter_work" | jq -r '.[0].number')
    work_url=$(printf '%s' "$iter_work" | jq -r '.[0].url')
    work_body=$(printf '%s' "$iter_work" | jq -r '.[0].body')
    work_head=$(printf '%s' "$iter_work" | jq -r '.[0].headRefName')
    MODE="iterate"
  else
    log "no work found, exiting cleanly"
    exit 0
  fi
fi

log "found work: $WORK_TYPE #$WORK_NUM ($MODE) — $work_url"

if [ "$DRY_RUN" -eq 1 ]; then
  log "DRY RUN — would claim, clone, and invoke claude"
  log "  mode: $MODE"
  if [ -n "$work_head" ]; then
    log "  head branch: $work_head"
  fi
  log "  body preview (first 20 lines):"
  printf '%s\n' "$work_body" | head -20 | sed 's/^/    | /' | tee -a "$LOG_FILE" >&2
  exit 0
fi

# ----- Phase 2: claim -----

log "claiming $WORK_TYPE #$WORK_NUM with 'In Progress' label"
gh_retry gh "$WORK_TYPE" edit "$WORK_NUM" -R "$REPO" --add-label "In Progress" >/dev/null
CLAIMED=1

# ----- Phase 3: shallow clone -----

CLONE_DIR="/tmp/wtf-worker-${WORK_NUM}-$(date -u +%Y%m%dT%H%M%SZ)"
log "cloning $REPO to $CLONE_DIR (--depth 1)"
git clone --depth 1 "git@github.com:$REPO.git" "$CLONE_DIR" 2>&1 | tee -a "$LOG_FILE" >&2

if [ "$MODE" = "iterate" ]; then
  cd "$CLONE_DIR"
  log "fetching PR head branch: $work_head"
  git fetch --depth 1 origin "$work_head":"$work_head" 2>&1 | tee -a "$LOG_FILE" >&2
  git checkout "$work_head"
fi

# ----- Phase 4: build prompt + invoke claude -----

if [ ! -f "$PROMPT_FILE" ]; then
  log "ERROR: prompt template not found at $PROMPT_FILE"
  exit 1
fi

# Assemble prompt: invocation-specific context preamble, then the template
# contents verbatim. Using printf rather than a heredoc avoids expansion
# surprises on the template body.
prompt=$(
  printf '# WTF worker invocation\n\n'
  printf -- '- **Mode:** %s\n' "$MODE"
  printf -- '- **Type:** %s\n' "$WORK_TYPE"
  printf -- '- **Number:** #%s\n' "$WORK_NUM"
  printf -- '- **URL:** %s\n' "$work_url"
  if [ -n "$work_head" ]; then
    printf -- '- **Head branch:** %s\n' "$work_head"
  fi
  printf '\n## Body of the %s\n\n' "$WORK_TYPE"
  printf '```\n%s\n```\n\n' "$work_body"
  printf -- '---\n\n'
  cat "$PROMPT_FILE"
)

log "invoking claude for $WORK_TYPE #$WORK_NUM"
cd "$CLONE_DIR"

# Claude handles all label management after this point (per the prompt):
#   - On success: leaves labels as the PR lifecycle dictates
#   - On partial success or no-action: removes "In Progress" and comments
#   - On iterate success: removes "In Progress" from the PR
# If claude -p itself fails, the trap removes "In Progress" as a fallback.
if ! claude -p "$prompt" \
     --model sonnet \
     --dangerously-skip-permissions \
     --no-session-persistence \
     2>&1 | tee -a "$LOG_FILE" >&2; then
  log "claude -p invocation returned non-zero"
  exit 1
fi

log "worker completed $WORK_TYPE #$WORK_NUM"
