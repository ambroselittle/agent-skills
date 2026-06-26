#!/usr/bin/env bash
# Notification hook entry point.
#
# Registered in ~/.claude/settings.json hooks.Notification.
# Shows a clickable macOS banner when Claude needs attention. Clicking
# focuses the window hosting this session: Ghostty notifications are
# emitted by the session's own terminal surface (exact tab focus),
# VS Code clicks open the workspace folder (focuses its existing
# window), and Superset-managed sessions activate the Superset app.
#
# Non-Ghostty paths require terminal-notifier
# (brew install terminal-notifier).

set -u

input=$(cat 2>/dev/null || true)
msg=$(printf '%s' "$input" | jq -r '.message // empty' 2>/dev/null) || msg=""
[ -n "$msg" ] || msg="Claude needs your attention"
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null) || cwd=""
[ -n "$cwd" ] || cwd="$PWD"

# The workspace/worktree root is what editors open as a window; fall
# back to the raw cwd outside a git checkout.
root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || root="$cwd"

# The hook runs detached from any tty, so walk up the process tree to
# the session's controlling terminal.
find_session_tty() {
  local pid=$$ tty_name
  while [ -n "$pid" ] && [ "$pid" -gt 1 ]; do
    tty_name=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$tty_name" ] && [ "$tty_name" != "??" ]; then
      printf '/dev/%s' "$tty_name"
      return 0
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  done
  return 1
}

# Ghostty ties an OSC 777 notification to the surface that emits it,
# so clicking the banner focuses this session's exact tab — no
# directory matching and no Automation permission needed. Ghostty
# suppresses it when the surface is already focused.
notify_ghostty_native() {
  local tty_dev
  tty_dev=$(find_session_tty) || return 1
  [ -w "$tty_dev" ] || return 1
  printf '\033]777;notify;Claude Code — %s;%s\033\\' \
    "$(basename "$root")" "$(printf '%s' "$msg" | tr -d '\000-\037')" \
    >"$tty_dev"
}

if [ "${TERM_PROGRAM:-}" = "ghostty" ] && notify_ghostty_native; then
  exit 0
fi

notifier=$(command -v terminal-notifier || true)
[ -n "$notifier" ] && [ -x "$notifier" ] || exit 0

focus="$HOME/.claude/hooks/focus-claude-session.sh"
common=(-title "Claude Code" -subtitle "$(basename "$root")" \
  -message "$msg" -sound Ping -group "claude-attention-$root")

case "${TERM_PROGRAM:-}" in
  vscode)
    bundle="${__CFBundleIdentifier:-com.microsoft.VSCode}"
    "$notifier" "${common[@]}" \
      -execute "$focus vscode $(printf '%q' "$root") $(printf '%q' "$bundle")"
    ;;
  ghostty)
    "$notifier" "${common[@]}" \
      -execute "$focus ghostty $(printf '%q' "$cwd") $(printf '%q' "$root")"
    ;;
  *)
    if [ -n "${SUPERSET_HOME_DIR:-}" ] ||
      [ "${__CFBundleIdentifier:-}" = "com.superset.desktop" ]; then
      # -sender fakes the posting app, so a click activates Superset;
      # -execute/-open are ignored when -sender is set.
      "$notifier" "${common[@]}" -sender com.superset.desktop
    elif [ -n "${__CFBundleIdentifier:-}" ]; then
      "$notifier" "${common[@]}" -activate "$__CFBundleIdentifier"
    else
      "$notifier" "${common[@]}"
    fi
    ;;
esac

exit 0
