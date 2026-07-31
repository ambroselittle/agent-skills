#!/usr/bin/env bash
# Sets the terminal window/tab title to "<color emoji> <topic>" so
# concurrent Claude Code sessions are distinguishable at a glance.
# Wired to SessionStart, UserPromptSubmit, and Stop so it re-asserts
# the title at the moments the terminal would otherwise overwrite it.

source "$HOME/.claude/hooks/window-lib.sh"

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] || cwd="$PWD"

idx=$(wlib_index "$sid")
emoji="${WLIB_EMOJI[$idx]}"
topic=$(wlib_topic "$sid" "$cwd")

seq=$(printf '\033]2;%s %s\007' "$emoji" "$topic")
jq -nc --arg seq "$seq" '{terminalSequence: $seq}'
