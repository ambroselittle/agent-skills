#!/bin/bash
# Installs or uninstalls the WTF worker launchd job by rendering
# templates/wtf-worker.plist.template into ~/Library/LaunchAgents/ and
# managing the launchctl lifecycle.
#
# Usage: wtf-worker-install.sh <install|uninstall> [--test]
#
# install [--test]: renders the plist, loads the job; with --test also
#                   fires an immediate run and tails the log for a few
#                   seconds so you can see it succeed.
# uninstall:        unloads the job and removes the plist.
#
# Called indirectly by `bash setup.sh --install-wtf-worker` /
# `--uninstall-wtf-worker`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$REPO_ROOT/templates/wtf-worker.plist.template"
LABEL="com.ambroselittle.wtf-worker"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"
WORKER_LOG="$LOG_DIR/wtf-worker.log"

mode="${1:-}"
test_flag=0
if [ "${2:-}" = "--test" ]; then
  test_flag=1
fi

case "$mode" in
  install)
    if [ ! -f "$TEMPLATE" ]; then
      echo "ERROR: template not found at $TEMPLATE" >&2
      exit 1
    fi

    mkdir -p "$(dirname "$PLIST_DEST")" "$LOG_DIR" "$HOME/.agent-skills"

    # Snapshot the user's gitconfig to a launchd-accessible location.
    #
    # macOS TCC blocks launchd agents from reading iCloud-synced paths
    # (~/Library/Mobile Documents/...). Users commonly symlink their
    # dotfiles into iCloud, which breaks git inside launchd ("unable to
    # access '~/.gitconfig': Operation not permitted"). We resolve the
    # symlink at install time (when we're in the user session and have
    # full permissions) and write a plain copy under ~/.agent-skills/,
    # which the launchd agent CAN read. The plist points
    # GIT_CONFIG_GLOBAL at that snapshot.
    GITCONFIG_SNAPSHOT="$HOME/.agent-skills/wtf-worker.gitconfig"
    if [ -r "$HOME/.gitconfig" ]; then
      cat "$HOME/.gitconfig" > "$GITCONFIG_SNAPSHOT"
      echo "  Gitconfig snapshot: $GITCONFIG_SNAPSHOT"
    else
      echo "⚠ ~/.gitconfig not readable — worker will use an empty git config." >&2
      : > "$GITCONFIG_SNAPSHOT"
    fi

    # Render placeholders. Using pipe separators in sed since paths contain /.
    sed -e "s|{{REPO_ROOT}}|$REPO_ROOT|g" \
        -e "s|{{HOME}}|$HOME|g" \
        "$TEMPLATE" > "$PLIST_DEST"

    # Idempotent reload: unload any previous version, then load.
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"

    echo "✓ Installed $LABEL"
    echo "  Plist:  $PLIST_DEST"
    echo "  Repo:   $REPO_ROOT"
    echo "  Logs:   $LOG_DIR/wtf-worker.log, wtf-worker.out.log, wtf-worker.err.log"
    echo "  Status: launchctl list | grep wtf-worker"
    echo "  Manual run: launchctl start $LABEL"

    if [ "$test_flag" -eq 1 ]; then
      echo ""
      echo "→ Firing an immediate test run..."
      launchctl start "$LABEL"
      sleep 3
      echo ""
      echo "--- Tail of $WORKER_LOG ---"
      tail -15 "$WORKER_LOG" 2>/dev/null || echo "(log not yet written — worker may still be starting)"
    fi
    ;;

  uninstall)
    if [ -f "$PLIST_DEST" ]; then
      launchctl unload "$PLIST_DEST" 2>/dev/null || true
      rm -f "$PLIST_DEST"
      echo "✓ Uninstalled $LABEL"
    else
      echo "· Not installed (no plist at $PLIST_DEST)"
    fi
    ;;

  ""|--help|-h)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    ;;

  *)
    echo "Unknown mode: $mode" >&2
    echo "Usage: wtf-worker-install.sh <install|uninstall> [--test]" >&2
    exit 1
    ;;
esac
