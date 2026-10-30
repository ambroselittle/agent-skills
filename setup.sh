#!/usr/bin/env bash
# Sets up agent skills: links skills, installs hooks, merges permissions,
# registers MCP servers, and upserts CLAUDE.md guidance.
# Idempotent — safe to re-run anytime.
#
# Everything is opt-in-able: name one or more components (see --list) to
# install just those, e.g. `setup.sh pretooluse` for only the hook engine.
# No arguments means the full setup. To keep something off a machine for good,
# list it under "exclude" in ~/.agent-skills/config.json (or pass --without,
# which writes that entry for you): excluded pieces are never installed and
# are removed if a previous run installed them.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Public setup always uses the shared dispatcher. Only its Claude-specific
# component phase enters the established shell installer below.
if [[ "${AGENT_SKILLS_INTERNAL_CLAUDE_COMPONENTS:-}" != 1 ]]; then
  _usable_python() {
    local candidate="$1" version major minor
    [[ -n "$candidate" && -x "$candidate" ]] || return 1
    version="$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null)" || return 1
    major="${version%%.*}"
    version="${version#*.}"
    minor="${version%%.*}"
    [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
    [[ "$major" -gt 3 || ( "$major" -eq 3 && "$minor" -ge 12 ) ]]
  }
  _python=""
  for _candidate in "${AGENT_SKILLS_PYTHON:-}" "$HOME/.agent-skills/scripts/python"; do
    if _usable_python "$_candidate"; then
      _python="$_candidate"
      break
    fi
  done
  if [[ -z "$_python" ]]; then
    for _name in python3 python3.15 python3.14 python3.13 python3.12 python; do
      _candidate="$(command -v "$_name" || true)"
      if _usable_python "$_candidate"; then
        _python="$_candidate"
        break
      fi
    done
  fi
  if [[ -z "$_python" ]] && command -v uv &>/dev/null; then
    _candidate="$(UV_PYTHON_DOWNLOADS=never uv python find '>=3.12' --no-python-downloads 2>/dev/null || true)"
    if _usable_python "$_candidate"; then
      _python="$_candidate"
    fi
  fi
  if [[ -z "$_python" ]]; then
    printf 'Python 3.12+ is required. Setup could not find a usable installed interpreter; nothing changed.\n' >&2
    exit 1
  fi
  export AGENT_SKILLS_PYTHON="$_python"
  "$_python" "$SCRIPT_DIR/scripts/setup_targets.py" "$@"
  exit $?
fi
CLAUDE_DIR="$HOME/.claude"
CLAUDE_SKILLS_DIR="$CLAUDE_DIR/skills"
CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"
HOOKS_DIR="$CLAUDE_DIR/hooks"

# --------------------------------------------------------------------------- #
# Subcommands — opt-in side installs that short-circuit the normal setup       #
# --------------------------------------------------------------------------- #

case "${1:-}" in
  --install-wtf-worker)
    exec "$SCRIPT_DIR/scripts/wtf-worker-install.sh" install "${2:-}"
    ;;
  --uninstall-wtf-worker)
    exec "$SCRIPT_DIR/scripts/wtf-worker-install.sh" uninstall
    ;;
esac

# --------------------------------------------------------------------------- #
# Components — each is an independently installable unit                      #
# --------------------------------------------------------------------------- #

ALL_COMPONENTS=(
  skills
  pretooluse
  notification
  message-display
  window-title
  attribution
  mcp
  guidance
  cli
)

# Group name → member components. Groups are just shorthand on the command line.
_expand_group() {
  case "$1" in
    hooks) printf 'pretooluse notification message-display window-title' ;;
    all)   printf '%s' "${ALL_COMPONENTS[*]}" ;;
    *)     return 1 ;;
  esac
}

_is_component() {
  local c
  for c in "${ALL_COMPONENTS[@]}"; do
    if [[ "$c" == "$1" ]]; then
      return 0
    fi
  done
  return 1
}

_describe_component() {
  case "$1" in
    skills)          printf 'Symlink skills into ~/.claude/skills' ;;
    pretooluse)      printf 'PreToolUse hook engine + rules, and the built-in allow/deny permissions' ;;
    notification)    printf 'macOS attention banners on Notification events (Darwin only)' ;;
    message-display) printf 'MessageDisplay phrase-swap hook' ;;
    window-title)    printf 'Per-session window titles, the window-title CLI, and the status line' ;;
    attribution)     printf 'Disable Claude auto-attribution (commit/PR trailers, session URL)' ;;
    mcp)             printf 'Register MCP servers (Playwright)' ;;
    guidance)        printf 'Upsert the <agent-skills-guidance> block in ~/.claude/CLAUDE.md' ;;
    cli)             printf 'Install claude-resume and the reclaude shell alias' ;;
  esac
}

_print_components() {
  printf "\nComponents (pass any number of names; default is all):\n"
  local c
  for c in "${ALL_COMPONENTS[@]}"; do
    printf "  %-16s %s\n" "$c" "$(_describe_component "$c")"
  done
  printf "\nGroups:\n"
  printf "  %-16s %s\n" "hooks" "pretooluse + notification + message-display + window-title"
  printf "  %-16s %s\n" "all" "every component (the default)"
}

_usage() {
  cat <<USAGE
Usage: setup.sh [--target claude|codex|both] [component|group ...] [flag ...]

Default (no arguments): idempotent full setup — links skills, installs hooks,
merges permissions, registers MCP servers, and updates CLAUDE.md.

Name one or more components to install only those for this run. A bare
'setup.sh' always means the full setup, minus anything listed under "exclude"
in ~/.agent-skills/config.json — excluded pieces are never installed and are
removed if a previous run installed them. Every key there is a list ("all"
excludes everything under that key):

  "exclude": {
    "hooks":       ["pretooluse", "notification", "message-display", "window-title"],
    "mcp":         ["playwright"],
    "guidance":    ["core", "personal"],
    "skills":      ["<skill name>", ...],
    "attribution": ["sessionUrl", "commit", "pr"],
    "cli":         ["claude-resume", "reclaude"]
  }

Examples:
  setup.sh                          Everything
  setup.sh pretooluse               Just the PreToolUse hook (engine + permissions)
  setup.sh hooks                    Every hook
  setup.sh skills guidance          Skills plus the CLAUDE.md guidance block
  setup.sh --without guidance mcp   Everything except those two

Flags:
  --target claude|codex|both         Select agent integrations (default: detect installed agents).
  --dry-run                        Preview selected changes without writing files.
  --without                        Persist every component named after this
                                   flag into the "exclude" key of
                                   ~/.claude/agent-skills.json, then remove
                                   what it installed. Sticks on every later
                                   run; edit the key to undo.
  --list                           List components and exit.
  --install-wtf-worker [--test]    Install the WTF worker launchd job.
                                   --test fires an immediate run and
                                   tails the log.
  --uninstall-wtf-worker           Uninstall the WTF worker launchd job.
  --no-clear                       Skip the terminal clear at setup start
                                   (useful when invoked from another script).
  --help, -h                       Show this message.
USAGE
  _print_components
}

# --------------------------------------------------------------------------- #
# Argument parsing                                                            #
# --------------------------------------------------------------------------- #

# Only clear on the default full run — a targeted run or a subcommand
# shouldn't wipe terminal scrollback.
DO_CLEAR=false
if [[ $# -eq 0 ]]; then
  DO_CLEAR=true
fi

_requested=""
_excluded=""
_exclude_mode=false

_add_names() {
  local target="$1" expanded name
  shift
  for name in "$@"; do
    if expanded="$(_expand_group "$name")"; then
      _add_names "$target" $expanded
      continue
    fi
    if ! _is_component "$name"; then
      printf "Unknown component or flag: %s\n" "$name" >&2
      printf "Run 'bash setup.sh --help' for usage.\n" >&2
      exit 1
    fi
    if [[ "$target" == include ]]; then
      [[ " $_requested " == *" $name "* ]] || _requested="$_requested $name"
    else
      [[ " $_excluded " == *" $name "* ]] || _excluded="$_excluded $name"
    fi
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      _usage
      exit 0
      ;;
    --list)
      _print_components
      exit 0
      ;;
    --no-clear)
      DO_CLEAR=false
      ;;
    --without)
      _exclude_mode=true
      ;;
    --install-wtf-worker|--uninstall-wtf-worker)
      printf "%s must be the first argument.\n" "$1" >&2
      exit 1
      ;;
    -*)
      printf "Unknown flag: %s\n" "$1" >&2
      printf "Run 'bash setup.sh --help' for usage.\n" >&2
      exit 1
      ;;
    *)
      if $_exclude_mode; then
        _add_names exclude "$1"
      else
        _add_names include "$1"
      fi
      ;;
  esac
  shift
done

if [[ -z "$_requested" ]]; then
  SELECTED=" ${ALL_COMPONENTS[*]} "
  IS_FULL_RUN=true
else
  SELECTED=" ${_requested# } "
  IS_FULL_RUN=false
fi


# True when the named component is part of this run.
_want() { [[ "$SELECTED" == *" $1 "* ]]; }

# True when any of the named components is part of this run.
_want_any() {
  local c
  for c in "$@"; do
    if _want "$c"; then
      return 0
    fi
  done
  return 1
}

if $DO_CLEAR; then
  clear
fi

# --------------------------------------------------------------------------- #
# UX helpers                                                                  #
# --------------------------------------------------------------------------- #

_bold="\033[1m"
_dim="\033[2m"
_green="\033[32m"
_yellow="\033[33m"
_red="\033[31m"
_cyan="\033[36m"
_reset="\033[0m"

section() { printf "\n${_bold}${_cyan}▸ %s${_reset}\n" "$1"; }
ok()      { printf "  ${_green}✓${_reset} %s\n" "$1"; }
skip()    { printf "  ${_dim}· %s${_reset}\n" "$1"; }
warn()    { printf "  ${_yellow}⚠ %s${_reset}\n" "$1"; }
fail()    { printf "  ${_red}✗ %s${_reset}\n" "$1"; }

printf "\n${_bold}🛠  Agent Skills Setup${_reset}\n"

if ! $IS_FULL_RUN; then
  printf "  ${_dim}Selected:${_reset}${SELECTED% }\n"
  printf "  ${_dim}Run 'setup.sh' with no arguments for the full setup.${_reset}\n"
fi

mkdir -p "$CLAUDE_DIR"

SETUP_CONFIG="$SCRIPT_DIR/scripts/setup_config.py"
export AGENT_SKILLS_CONFIG="${AGENT_SKILLS_CONFIG:-$HOME/.agent-skills/config.json}"

# Every settings.json / CLAUDE.md / shell-rc edit goes through the helper so
# install and uninstall share the same tested code.
_config() { "$AGENT_SKILLS_PYTHON" "$SETUP_CONFIG" "$@"; }

# Register a hook command under an event in settings.json, keyed on the command
# so a re-run updates an existing entry (e.g. a changed timeout) in place.
# Usage: _register_hook <event> <command> [timeout-seconds]
_register_hook() {
  _config hook register "$CLAUDE_SETTINGS" "$1" "$2" ${3:+--timeout "$3"}
}

# Remove every registration of <command> under <event>, pruning empty entries.
_unregister_hook() {
  _config hook unregister "$CLAUDE_SETTINGS" "$1" "$2"
}

# Delete the given paths (files or directories) that exist, reporting each.
_remove_paths() {
  local path removed=false
  for path in "$@"; do
    if [[ -e "$path" || -L "$path" ]]; then
      rm -rf "$path"
      ok "removed $path"
      removed=true
    fi
  done
  $removed || skip "nothing installed to remove"
}

# --------------------------------------------------------------------------- #
# Prerequisites                                                               #
# --------------------------------------------------------------------------- #

section "Checking prerequisites"

# The public bootstrap has already selected an installed Python 3.12+.
if [[ ! -x "${AGENT_SKILLS_PYTHON:-}" ]]; then
  fail "Selected Python 3.12+ runtime is unavailable — reapply setup"
  exit 1
fi
py_version="$("$AGENT_SKILLS_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
ok "Python $py_version"

if _want window-title; then
  if command -v jq &>/dev/null; then
    ok "jq"
  else
    fail "jq not found — the window-title hooks parse hook payloads with it"
    exit 1
  fi
fi

if _want guidance; then
  if command -v gh &>/dev/null; then
    ok "GitHub CLI (gh)"
  else
    warn "GitHub CLI (gh) not found — personal template lookup will be skipped"
  fi
fi

if _want mcp; then
  if command -v claude &>/dev/null; then
    ok "Claude CLI"
  else
    warn "Claude CLI not found — MCP server registration will be skipped"
  fi
fi

# --------------------------------------------------------------------------- #
# Exclusions — the persistent opt-out in ~/.agent-skills/config.json          #
# --------------------------------------------------------------------------- #

# One space-delimited set per exclude key (bash 3 has no associative arrays).
# "all" in a set excludes everything under that key.
_EXCL_hooks="" _EXCL_mcp="" _EXCL_guidance="" _EXCL_skills="" _EXCL_attribution="" _EXCL_cli=""

if [[ -n "$_excluded" ]]; then
  section "Persisting exclusions"
  for _name in $_excluded; do
    _config add-exclusion "$_name"
  done
  printf "  ${_dim}Saved to %s — edit its \"exclude\" key to undo.${_reset}\n" "$AGENT_SKILLS_CONFIG"
fi

while IFS='=' read -r _key _name; do
  [[ -n "$_key" ]] || continue
  _var="_EXCL_${_key}"
  printf -v "$_var" '%s %s' "${!_var}" "$_name"
done < <(_config exclusions)

# True when <name> under exclude key <key> is excluded, by name or by "all".
_is_excluded() {
  local var="_EXCL_$1" members
  members="${!var:-}"
  [[ " $members " == *" all "* || " $members " == *" $2 "* ]]
}

_excluded_summary=""
for _key in hooks mcp guidance skills attribution cli; do
  _var="_EXCL_${_key}"
  _members="${!_var# }"
  [[ -n "$_members" ]] && _excluded_summary="$_excluded_summary $_key:${_members// /,}"
done
if [[ -n "$_excluded_summary" ]]; then
  printf "\n  ${_dim}Excluded (%s):%s${_reset}\n" "$AGENT_SKILLS_CONFIG" "$_excluded_summary"
fi

# --------------------------------------------------------------------------- #
# [pretooluse] Install PreToolUse hook engine + rules                         #
# --------------------------------------------------------------------------- #

if _want pretooluse; then
  hook_source="$SCRIPT_DIR/hooks/PreToolUse/rules.json"
  hook_target_dir="$HOOKS_DIR/pre-tool-use"
  hook_target="$hook_target_dir/hook-rules.json"

  if _is_excluded hooks pretooluse; then
    section "Removing PreToolUse hook (excluded)"
    _remove_paths "$hook_target_dir" "$HOOKS_DIR/pre-tool-use.sh"
    _unregister_hook "PreToolUse" "~/.claude/hooks/pre-tool-use.sh"
  elif [[ -f "$hook_source" ]]; then
    section "Installing PreToolUse hook"
    mkdir -p "$hook_target_dir"

    # Engine
    if [[ -d "$SCRIPT_DIR/hooks/PreToolUse/engine" ]]; then
      [[ -d "$hook_target_dir/src" ]] && rm -rf "$hook_target_dir/src"
      rm -rf "$hook_target_dir/engine"
      cp -r "$SCRIPT_DIR/hooks/PreToolUse/engine" "$hook_target_dir/engine"
      ok "Hook engine"
    fi

    # Entry point
    if [[ -f "$SCRIPT_DIR/hooks/PreToolUse/pre-tool-use.sh" ]]; then
      cp "$SCRIPT_DIR/hooks/PreToolUse/pre-tool-use.sh" "$HOOKS_DIR/pre-tool-use.sh"
      chmod +x "$HOOKS_DIR/pre-tool-use.sh"
      ok "Entry point → $HOOKS_DIR/pre-tool-use.sh"
    fi

    # Rules
    cp "$hook_source" "$hook_target"
    ok "Hook rules"

    _register_hook "PreToolUse" "~/.claude/hooks/pre-tool-use.sh"

  else
    warn "$hook_source not found, skipping hook installation"
  fi
fi

# --------------------------------------------------------------------------- #
# [notification] Install Notification hook (macOS only)                       #
# --------------------------------------------------------------------------- #

if _want notification; then
  if [[ "$(uname)" != "Darwin" ]]; then
    # Only announce the skip when it was asked for explicitly — a full run on
    # Linux shouldn't report a component the platform can't have.
    if ! $IS_FULL_RUN; then
      section "Installing Notification hook"
      skip "notification is macOS-only — skipping on $(uname)"
    fi
  else
    notify_source_dir="$SCRIPT_DIR/hooks/Notification"

    if _is_excluded hooks notification; then
      section "Removing Notification hook (excluded)"
      _remove_paths "$HOOKS_DIR/notify-attention.sh" "$HOOKS_DIR/focus-claude-session.sh"
      _unregister_hook "Notification" "~/.claude/hooks/notify-attention.sh"
    elif [[ -f "$notify_source_dir/notify-attention.sh" ]]; then
      section "Installing Notification hook"
      mkdir -p "$HOOKS_DIR"
      cp "$notify_source_dir/notify-attention.sh" "$HOOKS_DIR/notify-attention.sh"
      cp "$notify_source_dir/focus-claude-session.sh" "$HOOKS_DIR/focus-claude-session.sh"
      chmod +x "$HOOKS_DIR/notify-attention.sh" "$HOOKS_DIR/focus-claude-session.sh"
      ok "Entry point → $HOOKS_DIR/notify-attention.sh"

      if ! command -v terminal-notifier >/dev/null 2>&1; then
        warn "terminal-notifier not installed (brew install terminal-notifier); hook will no-op until it is"
      fi

      _register_hook "Notification" "~/.claude/hooks/notify-attention.sh"

    else
      warn "$notify_source_dir/notify-attention.sh not found, skipping"
    fi
  fi
fi

# --------------------------------------------------------------------------- #
# [message-display] Install MessageDisplay hook (phrase swapping)             #
# --------------------------------------------------------------------------- #

if _want message-display; then
  swap_source_dir="$SCRIPT_DIR/hooks/MessageDisplay"
  swap_target_dir="$HOOKS_DIR/message-display"

  if _is_excluded hooks message-display; then
    section "Removing MessageDisplay hook (excluded)"
    _remove_paths "$swap_target_dir"
    _unregister_hook "MessageDisplay" "~/.claude/hooks/message-display/swap.py"
  elif [[ -f "$swap_source_dir/swap.py" ]]; then
    section "Installing MessageDisplay hook"
    mkdir -p "$swap_target_dir"
    cp "$swap_source_dir/swap.py" "$swap_target_dir/swap.py"
    chmod +x "$swap_target_dir/swap.py"
    ok "Entry point → $swap_target_dir/swap.py"

    # phrases.json is the shipped word list; personal additions live in
    # ~/.agent-skills/local-phrases.json and are never overwritten here.
    cp "$swap_source_dir/phrases.json" "$swap_target_dir/phrases.json"
    ok "Phrase list"

    # Fires on every flush of every streaming message — cap it well under the
    # 10s default so a wedged hook can't stall rendering for long.
    _register_hook "MessageDisplay" "~/.claude/hooks/message-display/swap.py" 5
  else
    warn "$swap_source_dir/swap.py not found, skipping"
  fi
fi

# --------------------------------------------------------------------------- #
# [window-title] Install per-session window titles and the status line        #
# --------------------------------------------------------------------------- #

if _want window-title; then
  wt_source_dir="$SCRIPT_DIR/hooks/WindowTitle"

  if _is_excluded hooks window-title; then
    section "Removing window titles (excluded)"
    _remove_paths "$HOOKS_DIR/window-lib.sh" "$HOOKS_DIR/window-tag.sh" "$HOOKS_DIR/window-nudge.sh" \
      "$CLAUDE_DIR/scripts/window-title" "$CLAUDE_DIR/statusline.sh" "$CLAUDE_DIR/window-labels"
    for _wt_event in SessionStart UserPromptSubmit Stop; do
      _unregister_hook "$_wt_event" "~/.claude/hooks/window-tag.sh"
    done
    for _wt_event in SessionStart UserPromptSubmit; do
      _unregister_hook "$_wt_event" "~/.claude/hooks/window-nudge.sh"
    done
    _config statusline unset "$CLAUDE_SETTINGS" "~/.claude/statusline.sh"
    _config env unset "$CLAUDE_SETTINGS" CLAUDE_CODE_DISABLE_TERMINAL_TITLE 1
  elif [[ -f "$wt_source_dir/window-lib.sh" ]]; then
    section "Installing window titles"
    mkdir -p "$HOOKS_DIR" "$CLAUDE_DIR/scripts" "$CLAUDE_DIR/window-labels"

    cp "$wt_source_dir/window-lib.sh" "$HOOKS_DIR/window-lib.sh"
    cp "$wt_source_dir/window-tag.sh" "$HOOKS_DIR/window-tag.sh"
    cp "$wt_source_dir/window-nudge.sh" "$HOOKS_DIR/window-nudge.sh"
    chmod +x "$HOOKS_DIR/window-tag.sh" "$HOOKS_DIR/window-nudge.sh"
    ok "Hooks → $HOOKS_DIR/window-{tag,nudge}.sh"

    cp "$wt_source_dir/window-title" "$CLAUDE_DIR/scripts/window-title"
    chmod +x "$CLAUDE_DIR/scripts/window-title"
    ok "CLI → $CLAUDE_DIR/scripts/window-title"

    cp "$wt_source_dir/statusline.sh" "$CLAUDE_DIR/statusline.sh"
    chmod +x "$CLAUDE_DIR/statusline.sh"
    ok "Status line → $CLAUDE_DIR/statusline.sh"

    # The title is re-asserted at every point the terminal would otherwise
    # overwrite it; the reminder only needs the two events that can carry
    # additional context into the conversation.
    for _wt_event in SessionStart UserPromptSubmit Stop; do
      _register_hook "$_wt_event" "~/.claude/hooks/window-tag.sh"
    done
    for _wt_event in SessionStart UserPromptSubmit; do
      _register_hook "$_wt_event" "~/.claude/hooks/window-nudge.sh"
    done

    _config statusline set "$CLAUDE_SETTINGS" "~/.claude/statusline.sh"

    # Claude Code owns the title only when its own title-setting is off,
    # otherwise it overwrites the hook's escape sequence on every render.
    _config env set "$CLAUDE_SETTINGS" CLAUDE_CODE_DISABLE_TERMINAL_TITLE 1

  else
    warn "$wt_source_dir/window-lib.sh not found, skipping"
  fi
fi

# --------------------------------------------------------------------------- #
# [pretooluse] Merge built-in rules into settings.json permissions            #
# --------------------------------------------------------------------------- #

if _want pretooluse; then
  builtin_rules="$SCRIPT_DIR/hooks/PreToolUse/built-in-rules.json"

  if [[ ! -f "$builtin_rules" ]]; then
    section "Merging permissions"
    warn "$builtin_rules not found, skipping permissions merge"
  elif _is_excluded hooks pretooluse; then
    section "Removing built-in permissions (excluded)"
    _config permissions remove "$CLAUDE_SETTINGS" "$builtin_rules"
  else
    section "Merging permissions"
    _config permissions merge "$CLAUDE_SETTINGS" "$builtin_rules"
  fi
fi

# --------------------------------------------------------------------------- #
# [attribution] Disable Claude auto-attribution (commit/PR trailers + URL)    #
# --------------------------------------------------------------------------- #

if _want attribution; then
  section "Disabling Claude auto-attribution"

  # We append our own trailers manually (see ~/.claude/CLAUDE.md), so turn off
  # Claude Code's auto-attribution to avoid duplicates:
  #   attribution.sessionUrl = false  → drop the session-URL line
  #   attribution.commit      = ""     → no auto commit trailer
  #   attribution.pr          = ""     → no auto PR trailer
  # An excluded key is deleted (only while it still holds our value) so Claude
  # Code falls back to its default for it.
  _attr_set=""
  _attr_unset=""
  for _attr_key in sessionUrl commit pr; do
    if _is_excluded attribution "$_attr_key"; then
      _attr_unset="$_attr_unset $_attr_key"
    else
      _attr_set="$_attr_set $_attr_key"
    fi
  done
  if [[ -n "$_attr_set" ]]; then
    _config attribution set "$CLAUDE_SETTINGS" $_attr_set
  fi
  if [[ -n "$_attr_unset" ]]; then
    _config attribution unset "$CLAUDE_SETTINGS" $_attr_unset
  fi
fi

# --------------------------------------------------------------------------- #
# [mcp] Register MCP servers                                                  #
# --------------------------------------------------------------------------- #

if _want mcp; then
  section "Registering MCP servers"

  _register_mcp() {
    local name="$1"
    local check_cmd="$2"
    shift 2
    # Check if already registered by looking for the command in mcp list output.
    # We match on command (not name) since users may register under a different name.
    if command -v claude &>/dev/null && claude mcp list 2>/dev/null | grep -q "$check_cmd"; then
      skip "$name already registered"
      return
    fi

    if ! command -v claude &>/dev/null; then
      skip "$name — claude CLI not available"
      return
    fi

    if claude mcp add --scope user "$name" "$@" 2>/dev/null; then
      ok "$name"
    else
      warn "$name — registration failed (run manually: claude mcp add --scope user $name $*)"
    fi
  }

  _unregister_mcp() {
    local name="$1"
    local check_cmd="$2"
    if ! command -v claude &>/dev/null; then
      skip "$name — claude CLI not available"
      return
    fi
    # Only remove a registration that carries our command — a server the user
    # registered under the same name with a different command is theirs.
    if ! claude mcp get "$name" 2>/dev/null | grep -q "$check_cmd"; then
      skip "$name excluded — not registered by us, left alone"
      return
    fi
    if claude mcp remove --scope user "$name" >/dev/null 2>&1; then
      ok "removed $name (excluded)"
    else
      warn "$name — removal failed (run manually: claude mcp remove --scope user $name)"
    fi
  }

  # One line per server: excluded servers are removed, the rest registered.
  _mcp_server() {
    if _is_excluded mcp "$1"; then
      _unregister_mcp "$1" "$2"
    else
      _register_mcp "$@"
    fi
  }

  _mcp_server "playwright" "@playwright/mcp" -- npx @playwright/mcp@latest
fi

# --------------------------------------------------------------------------- #
# [cli] Install CLI scripts                                                   #
# --------------------------------------------------------------------------- #

if _want cli; then
  section "Installing CLI scripts"

  SCRIPTS_TARGET_DIR="$CLAUDE_DIR/scripts"
  mkdir -p "$SCRIPTS_TARGET_DIR"

  # claude-resume
  _resume_source="$SCRIPT_DIR/scripts/claude-resume/claude-resume.sh"
  _resume_target="$SCRIPTS_TARGET_DIR/claude-resume.sh"

  if _is_excluded cli claude-resume; then
    if [[ -L "$_resume_target" ]] && [[ "$(readlink "$_resume_target")" == *"/scripts/claude-resume/claude-resume.sh" ]]; then
      rm -f "$_resume_target"
      ok "removed claude-resume (excluded)"
    elif [[ -e "$_resume_target" || -L "$_resume_target" ]]; then
      skip "claude-resume excluded, but $_resume_target is not ours — left alone"
    fi
  elif [[ -f "$_resume_source" ]]; then
    if [[ -L "$_resume_target" ]]; then
      existing="$(readlink "$_resume_target")"
      if [[ "$existing" == "$_resume_source" ]]; then
        skip "claude-resume already linked"
      else
        rm -f "$_resume_target"
        ln -s "$_resume_source" "$_resume_target"
        ok "claude-resume (updated link)"
      fi
    else
      [[ -f "$_resume_target" ]] && rm -f "$_resume_target"
      ln -s "$_resume_source" "$_resume_target"
      ok "claude-resume"
    fi
  else
    warn "claude-resume source not found, skipping"
  fi

  # Shell alias: re-claude
  _shell_rc=""
  case "$SHELL" in
    */zsh)  _shell_rc="$HOME/.zshrc" ;;
    */bash) _shell_rc="$HOME/.bash_profile" ;;
  esac

  if [[ -n "$_shell_rc" ]] && [[ -f "$_shell_rc" ]]; then
    if _is_excluded cli reclaude; then
      _config rcfence remove "$_shell_rc"
    else
      _config rcfence upsert "$_shell_rc" - <<'ALIASES'
# BEGIN agent-skills-aliases — managed by agent-skills setup, do not edit manually
alias reclaude="$HOME/.claude/scripts/claude-resume.sh"
# END agent-skills-aliases
ALIASES
    fi
  else
    skip "Shell aliases — unsupported shell or missing rc file"
  fi
fi

# --------------------------------------------------------------------------- #
# Done                                                                        #
# --------------------------------------------------------------------------- #

if $IS_FULL_RUN; then
  printf "\n${_bold}${_green}✓ Setup complete${_reset}\n"
  printf "  Rerun this at any time to update your CLAUDE.md, skills, and hooks.\n\n"
else
  printf "\n${_bold}${_green}✓ Setup complete${_reset}${_dim} —${SELECTED% }${_reset}\n"
  printf "  Run 'bash setup.sh --list' to see everything else available.\n\n"
fi
