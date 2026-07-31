#!/usr/bin/env bash
# Reminds the session to give its window a topical title, so tabbing between
# several open Claude windows is a matter of reading labels rather than
# reconstructing what each one was about.
#
# The gating is entirely deterministic — this hook never guesses a title, it
# only decides when the model should. Wired to UserPromptSubmit (where the
# reminder rides along with the prompt, costing no extra turn) and to
# SessionStart, which fires with source "compact" right after a recap and is
# therefore a natural moment to re-check that the topic still holds.
#
# A pinned title is the user's own and silences this entirely.

source "$HOME/.claude/hooks/window-lib.sh"

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
event=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')
source_kind=$(printf '%s' "$input" | jq -r '.source // empty')

[ -n "$sid" ] || exit 0
wlib_is_pinned "$sid" && exit 0

turns=$(wlib_turn_count "$transcript")
nudged=$(wlib_meta "$sid" nudged 0)
set_at=$(wlib_meta "$sid" turns 0)

is_compact=false
if [ "$event" = SessionStart ] && [ "$source_kind" = compact ]; then
  is_compact=true
fi

# Back off when a previous reminder went unheeded, so it never nags per-turn.
# A compaction is rare and is the strongest signal that the topic has moved,
# so it is always worth a look regardless of recent reminders.
if ! $is_compact &&
   [ "$nudged" -gt 0 ] &&
   [ $((turns - nudged)) -lt "$WLIB_NUDGE_BACKOFF" ]; then
  exit 0
fi

message=""

if ! label=$(wlib_stored_label "$sid"); then
  # No title yet. Only prompt where there is a conversation to infer from —
  # at SessionStart there is nothing to go on.
  if [ "$event" = UserPromptSubmit ]; then
    message="This window has no title yet. Now that you can see what this conversation is about, set one: run \`~/.claude/scripts/window-title set \"<topic>\"\` with a scannable three-or-four-word topic. Name the subject in plain words — never a ticket key, PR number, or branch name. Do it quietly as part of this turn — don't announce it or ask first."
  fi
elif $is_compact; then
  message="The conversation was just compacted. Check that the window title \"$label\" still describes it; if the topic has moved on, run \`~/.claude/scripts/window-title set \"<topic>\"\`. Leave it alone if it still fits."
elif [ $((turns - set_at)) -ge "$WLIB_STALE_AFTER" ]; then
  message="It has been $((turns - set_at)) turns since the window title was set to \"$label\". If the topic has drifted, run \`~/.claude/scripts/window-title set \"<topic>\"\`. Leave it alone if it still fits."
fi

[ -n "$message" ] || exit 0

if [ -n "$label" ]; then
  wlib_write "$sid" "$label" "$(wlib_meta "$sid" mode auto)" "$set_at" "$turns"
else
  # Record the reminder without inventing a label — an empty first line keeps
  # wlib_stored_label reporting "unset" while the backoff counter persists.
  mkdir -p "$WLIB_LABELS_DIR"
  printf '\nmode=auto\nturns=0\nnudged=%s\n' "$turns" >"$(wlib_label_file "$sid")"
fi

jq -nc --arg event "$event" --arg msg "$message" \
  '{hookSpecificOutput: {hookEventName: $event, additionalContext: $msg}}'
