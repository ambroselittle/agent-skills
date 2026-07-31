#!/usr/bin/env bash
# Claude Code status line: a colored band keyed to the session so each
# window is visually distinct, then where you are (working directory, and
# branch when that directory is a git repo), model, context, and cost.
#
# Location lives here rather than in the window title on purpose — the title
# carries the conversation's topic, this answers "where am I right now".

source "$HOME/.claude/hooks/window-lib.sh"

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -n "$cwd" ] || cwd="$PWD"
model=$(printf '%s' "$input" | jq -r '.model.display_name // "?"')
pct=$(printf '%s' "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
cost=$(printf '%s' "$input" | jq -r '.cost.total_cost_usd // 0')

idx=$(wlib_index "$sid")
emoji="${WLIB_EMOJI[$idx]}"
rgb=$(wlib_rgb "${WLIB_HEX[$idx]}")
location=$(wlib_location "$cwd")
costf=$(printf '%.2f' "$cost" 2>/dev/null || echo 0.00)

esc=$'\033'
c="${esc}[1;38;2;${rgb}m"
d="${esc}[2m"
r="${esc}[0m"

printf '%s' "${c}${emoji} ${location}${r} ${d}·${r} ${model} ${d}·${r} ctx ${c}${pct}%${r} ${d}·${r} \$${costf}"
