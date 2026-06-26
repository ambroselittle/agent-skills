#!/usr/bin/env bash
# Click handler for Claude attention notifications (notify-attention.sh).
# Brings the window hosting the given session directory to the front.
#
# Usage:
#   focus-claude-session.sh vscode <workspace-root> [bundle-id]
#   focus-claude-session.sh ghostty <session-cwd> [workspace-root]
#
# Runs in terminal-notifier's context on click, so it must not assume
# the session's environment (PATH, cwd) and macOS attributes its
# Automation permission to terminal-notifier.

set -u
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

mode=${1:?mode}
shift

canonical() {
  realpath "$1" 2>/dev/null || printf '%s' "$1"
}

focus_vscode() {
  local dir=${1:?dir} bundle=${2:-com.microsoft.VSCode}
  # Opening a folder that is already open focuses its existing window.
  open -b "$bundle" "$dir"
}

focus_ghostty() {
  local dir target root match="" fallback="" line tid twd
  dir=${1:?dir}
  target=$(canonical "$dir")
  root=$(canonical "${2:-$dir}")

  # Ghostty reports working directories as the shell announced them
  # (possibly via a symlinked path), so canonicalize before comparing.
  while IFS='|' read -r tid twd; do
    [ -n "$tid" ] && [ -n "$twd" ] || continue
    twd=$(canonical "$twd")
    if [ "$twd" = "$target" ]; then
      match=$tid
      break
    fi
    if [ -z "$fallback" ] && [ "$twd" = "$root" ]; then
      fallback=$tid
    fi
  done < <(osascript -e 'tell application "Ghostty"
    set out to ""
    repeat with t in terminals
      try
        set out to out & (id of t) & "|" & (working directory of t) & linefeed
      end try
    end repeat
    return out
  end tell')

  [ -n "$match" ] || match=$fallback
  if [ -n "$match" ]; then
    osascript \
      -e "tell application \"Ghostty\" to focus terminal id \"$match\"" \
      -e 'tell application "Ghostty" to activate'
  else
    open -b com.mitchellh.ghostty
  fi
}

case "$mode" in
  vscode) focus_vscode "$@" ;;
  ghostty) focus_ghostty "$@" ;;
  *)
    echo "unknown mode: $mode" >&2
    exit 1
    ;;
esac
