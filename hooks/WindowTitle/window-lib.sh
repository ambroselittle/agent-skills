#!/usr/bin/env bash
# Shared helpers for per-session window tagging.
#
# Two independent surfaces, deliberately carrying different information:
#   - terminal title  → the conversation's *topic*, for scanning tabs
#   - status line     → *where you are*: working directory + git branch
#
# Color is derived from the session id, so a window keeps one hue for life.

WLIB_LABELS_DIR="$HOME/.claude/window-labels"

# Turns since the label was set before the stale-topic reminder fires.
WLIB_STALE_AFTER=10

# Minimum turns between reminders, so an ignored one doesn't nag every turn.
WLIB_NUDGE_BACKOFF=5

# Prefixes dropped from displayed paths, longest first. These are the roots
# everything already lives under, so printing them says nothing and crowds out
# the part that identifies the directory. $HOME is always shortened to ~.
WLIB_PATH_STRIP=(
  /Volumes/Code
)

WLIB_EMOJI=(
  $'\xf0\x9f\x94\xb4'  # red
  $'\xf0\x9f\x9f\xa0'  # orange
  $'\xf0\x9f\x9f\xa1'  # yellow
  $'\xf0\x9f\x9f\xa2'  # green
  $'\xf0\x9f\x94\xb5'  # blue
  $'\xf0\x9f\x9f\xa3'  # purple
  $'\xf0\x9f\x9f\xa4'  # brown
  $'\xe2\x9a\xaa'      # white
)
WLIB_HEX=(e74c3c e67e22 f1c40f 2ecc71 3498db 9b59b6 a86b4c d5dbdb)

wlib_index() {
  local key="${1:-x}"
  [ -n "$key" ] || key="x"
  local hex
  if command -v md5 >/dev/null 2>&1; then
    hex=$(printf '%s' "$key" | md5)
  elif command -v md5sum >/dev/null 2>&1; then
    hex=$(printf '%s' "$key" | md5sum | cut -d' ' -f1)
  fi
  if [ -n "$hex" ]; then
    hex=${hex: -8}
    printf '%s' "$(( 0x$hex % ${#WLIB_EMOJI[@]} ))"
  else
    local sum
    sum=$(printf '%s' "$key" | cksum | cut -d' ' -f1)
    printf '%s' "$(( sum % ${#WLIB_EMOJI[@]} ))"
  fi
}

wlib_rgb() {
  local hex="$1"
  printf '%d;%d;%d' "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}

# --------------------------------------------------------------------------- #
# Applicability                                                                #
# --------------------------------------------------------------------------- #

# True when this session is attached to something with a title bar to set.
#
# The title itself is OSC 2, which every terminal either honours or discards,
# so terminal *type* needs no check — an IDE's integrated terminal is as valid
# a target as Ghostty. What does need one is a session with no window at all:
# a scripted -p run, CI, or a cloud session, where the reminder would spend a
# turn naming a window nobody can see.
wlib_has_window() {
  case "${CLAUDE_CODE_ENTRYPOINT:-}" in
    sdk-*|github-actions|cloud) return 1 ;;
  esac
  case "${TERM:-}" in
    ''|dumb) return 1 ;;
  esac
  return 0
}

# --------------------------------------------------------------------------- #
# Label store                                                                  #
# --------------------------------------------------------------------------- #
#
# One file per session at $WLIB_LABELS_DIR/<session-id>:
#   line 1  the label itself
#   line 2+ key=value metadata
#
# Metadata keys:
#   mode    auto (agent-chosen, may be revised) or pinned (user's, never touched)
#   turns   user-turn count when the label was written
#   nudged  user-turn count when a reminder was last emitted
#
# Line 1 is the label with no prefix so anything can read it with `head -n1`.

wlib_label_file() {
  printf '%s/%s' "$WLIB_LABELS_DIR" "$1"
}

wlib_stored_label() {
  local file
  file=$(wlib_label_file "$1")
  [ -s "$file" ] || return 1
  local label
  label=$(head -n1 "$file")
  [ -n "$label" ] || return 1
  printf '%s' "$label"
}

# Reads one metadata key. A label file without metadata (hand-written, or
# from an older layout) reads as mode=auto with zeroed counters.
wlib_meta() {
  local sid="$1" key="$2" file value
  file=$(wlib_label_file "$sid")
  [ -s "$file" ] || { printf '%s' "$3"; return; }
  value=$(sed -n "2,\$p" "$file" | grep -m1 "^$key=" | cut -d= -f2-)
  printf '%s' "${value:-$3}"
}

wlib_is_pinned() {
  [ "$(wlib_meta "$1" mode auto)" = pinned ]
}

# Writes the label, preserving any metadata key not passed here.
# Usage: wlib_write <sid> <label> <mode> [turns] [nudged]
wlib_write() {
  local sid="$1" label="$2" mode="$3" turns="${4:-}" nudged="${5:-}" file
  file=$(wlib_label_file "$sid")
  mkdir -p "$WLIB_LABELS_DIR"
  [ -n "$turns" ] || turns=$(wlib_meta "$sid" turns 0)
  [ -n "$nudged" ] || nudged=$(wlib_meta "$sid" nudged 0)
  printf '%s\nmode=%s\nturns=%s\nnudged=%s\n' \
    "$label" "$mode" "$turns" "$nudged" >"$file"
}

# --------------------------------------------------------------------------- #
# Transcript inspection                                                        #
# --------------------------------------------------------------------------- #

# Counts real user turns, skipping tool-result and meta entries — both of
# which are recorded with type "user" and would otherwise inflate the count
# by an order of magnitude.
wlib_turn_count() {
  local transcript="$1"
  [ -f "$transcript" ] || { printf '0'; return; }
  jq -r '
    select(.type == "user")
    | select(.isMeta != true)
    | (.message.content) as $content
    | if ($content | type) == "string" then "turn"
      elif ($content | type) == "array" and (any($content[]; .type == "text")) then "turn"
      else empty end' "$transcript" 2>/dev/null | wc -l | tr -d ' '
}

# Locates a session transcript by id, for callers that only have the id
# (the CLI) rather than the path (the hooks).
wlib_find_transcript() {
  local sid="$1"
  [ -n "$sid" ] || return 1
  find "$HOME/.claude/projects" -maxdepth 2 -name "$sid.jsonl" -print -quit 2>/dev/null \
    | grep . || return 1
}

# --------------------------------------------------------------------------- #
# Display strings                                                              #
# --------------------------------------------------------------------------- #

# The path as written, minus a leading root that carries no information:
# $HOME becomes ~, and anything in WLIB_PATH_STRIP is dropped outright.
# Every remaining component is printed in full — an abbreviated component
# has to be decoded, which is the opposite of what a status line is for.
wlib_path() {
  local path="${1:-$PWD}" strip
  case "$path" in
    "$HOME")    printf '~'; return ;;
    "$HOME"/*)  printf '~/%s' "${path#"$HOME"/}"; return ;;
  esac
  for strip in "${WLIB_PATH_STRIP[@]}"; do
    case "$path" in
      "$strip"/*) printf '%s' "${path#"$strip"/}"; return ;;
    esac
  done
  printf '%s' "$path"
}

wlib_branch() {
  local cwd="${1:-$PWD}" branch
  branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
  if [ -z "$branch" ]; then
    branch=$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null) || return 1
  fi
  [ -n "$branch" ] || return 1
  printf '%s' "$branch"
}

# Status line: always location, never the topic. Answers "where am I right
# now" — which the title deliberately no longer does.
wlib_location() {
  local cwd="${1:-$PWD}" path branch
  path=$(wlib_path "$cwd")
  if branch=$(wlib_branch "$cwd"); then
    printf '%s ‹%s›' "$path" "$branch"
  else
    printf '%s' "$path"
  fi
}

# Window title: the conversation's topic. Falls back to the directory name
# only for the turn or two before a topic has been chosen.
wlib_topic() {
  local sid="$1" cwd="${2:-$PWD}"
  wlib_stored_label "$sid" && return
  basename "$cwd"
}
