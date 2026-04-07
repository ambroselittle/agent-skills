#!/usr/bin/env bash
# Sets up agent skills: links skills, installs hooks, merges permissions,
# registers MCP servers, and upserts CLAUDE.md guidance.
# Idempotent — safe to re-run anytime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CLAUDE_SKILLS_DIR="$CLAUDE_DIR/skills"
CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
HOOKS_DIR="$CLAUDE_DIR/hooks"

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

mkdir -p "$CLAUDE_SKILLS_DIR"

# --------------------------------------------------------------------------- #
# Prerequisites                                                               #
# --------------------------------------------------------------------------- #

section "Checking prerequisites"

if ! command -v python3 &>/dev/null; then
  fail "python3 not found — the hook engine requires Python 3.11+"
  exit 1
fi

py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
py_major="${py_version%%.*}"
py_minor="${py_version##*.}"
if [[ "$py_major" -lt 3 ]] || { [[ "$py_major" -eq 3 ]] && [[ "$py_minor" -lt 11 ]]; }; then
  fail "Python $py_version found, but 3.11+ required (for union type syntax)"
  printf "     Install a newer Python or update your PATH.\n"
  exit 1
fi
ok "Python $py_version"

if command -v gh &>/dev/null; then
  ok "GitHub CLI (gh)"
else
  warn "GitHub CLI (gh) not found — personal template lookup will be skipped"
fi

if command -v claude &>/dev/null; then
  ok "Claude CLI"
else
  warn "Claude CLI not found — MCP server registration will be skipped"
fi

# --------------------------------------------------------------------------- #
# Worktree detection                                                          #
# --------------------------------------------------------------------------- #

IS_WORKTREE=false
MAIN_REPO=""

if git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
  worktree_root="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
  git_common="$(git -C "$SCRIPT_DIR" rev-parse --git-common-dir)"
  main_repo="$(cd "$git_common" && cd .. && pwd)"

  if [[ "$worktree_root" != "$main_repo" ]]; then
    IS_WORKTREE=true
    MAIN_REPO="$main_repo"
  fi
fi

# --------------------------------------------------------------------------- #
# 1. Link skills                                                              #
# --------------------------------------------------------------------------- #

section "Linking skills"

if $IS_WORKTREE; then
  printf "  ${_dim}Worktree mode — only linking skills changed on this branch${_reset}\n"
fi

# In a worktree: only relink skills with changes on the current branch.
# Everything else stays linked to main repo.
_changed_skills=()
if $IS_WORKTREE; then
  while IFS= read -r file; do
    if [[ "$file" == skills/* ]]; then
      skill="${file#skills/}"
      skill="${skill%%/*}"
      _changed_skills+=("$skill")
    fi
  done < <(
    git -C "$SCRIPT_DIR" diff --name-only main... -- skills/ 2>/dev/null
    git -C "$SCRIPT_DIR" diff --name-only -- skills/ 2>/dev/null
    git -C "$SCRIPT_DIR" ls-files --others --exclude-standard -- skills/ 2>/dev/null
  )
  _changed_skills=($(printf '%s\n' "${_changed_skills[@]}" | sort -u))
fi

_should_link_skill() {
  local skill_name="$1"
  if ! $IS_WORKTREE; then
    return 0
  fi
  for s in "${_changed_skills[@]}"; do
    [[ "$s" == "$skill_name" ]] && return 0
  done
  return 1
}

_linked=0
_skipped=0
for skill_dir in "$SCRIPT_DIR"/skills/*/; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"
  [[ -f "$skill_dir/SKILL.md" ]] || continue

  if ! _should_link_skill "$skill_name"; then
    ((_skipped++)) || true
    continue
  fi

  target="$CLAUDE_SKILLS_DIR/$skill_name"

  if [[ -L "$target" ]]; then
    existing="$(readlink "$target")"
    if [[ "$existing" == "$skill_dir" || "$existing" == "${skill_dir%/}" ]]; then
      ((_skipped++)) || true
      continue
    fi
    rm -f "$target"
  elif [[ -e "$target" ]]; then
    warn "$skill_name: non-symlink exists at $target, skipping"
    continue
  fi

  ln -s "${skill_dir%/}" "$target"
  if $IS_WORKTREE; then
    ok "$skill_name → worktree"
  else
    ok "$skill_name"
  fi
  ((_linked++)) || true
done

# Link shared resources
shared_source="$SCRIPT_DIR/skills/shared"
shared_target="$CLAUDE_SKILLS_DIR/shared"

if [[ -d "$shared_source" ]]; then
  _link_shared=true
  if $IS_WORKTREE && [[ ${#_changed_skills[@]} -eq 0 ]]; then
    _link_shared=false
  fi

  if $_link_shared; then
    if [[ -L "$shared_target" ]]; then
      existing="$(readlink "$shared_target")"
      if [[ "$existing" != "$shared_source" ]]; then
        rm -f "$shared_target"
        ln -s "$shared_source" "$shared_target"
        ok "shared"
        ((_linked++)) || true
      fi
    elif [[ ! -e "$shared_target" ]]; then
      ln -s "$shared_source" "$shared_target"
      ok "shared"
      ((_linked++)) || true
    fi
  fi
fi

if [[ $_linked -eq 0 ]]; then
  skip "All skills already linked ($_skipped up to date)"
else
  printf "  ${_dim}$_linked linked, $_skipped already up to date${_reset}\n"
fi

# --------------------------------------------------------------------------- #
# 2. Install PreToolUse hook                                                  #
# --------------------------------------------------------------------------- #

section "Installing PreToolUse hook"

hook_source="$SCRIPT_DIR/hooks/PreToolUse/rules.json"
hook_target_dir="$HOOKS_DIR/pre-tool-use"
hook_target="$hook_target_dir/hook-rules.json"

if [[ -f "$hook_source" ]]; then
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

  # Ensure hook is registered in settings.json
  python3 - "$CLAUDE_SETTINGS" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]
hook_command = "~/.claude/hooks/pre-tool-use.sh"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

hooks = settings.setdefault("hooks", {})
pre_tool_use = hooks.setdefault("PreToolUse", [])

# Check if already registered
already = any(
    hook_command in h.get("command", "")
    for entry in pre_tool_use
    for h in entry.get("hooks", [])
)

if not already:
    pre_tool_use.append({
        "hooks": [{"type": "command", "command": hook_command}]
    })
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  \033[32m✓\033[0m Hook registered in settings.json")
else:
    print("  \033[2m· Hook already registered in settings.json\033[0m")
PYEOF

else
  warn "$hook_source not found, skipping hook installation"
fi

# --------------------------------------------------------------------------- #
# 3. Merge built-in rules into settings.json permissions                      #
# --------------------------------------------------------------------------- #

section "Merging permissions"

builtin_rules="$SCRIPT_DIR/hooks/PreToolUse/built-in-rules.json"

if [[ -f "$builtin_rules" ]]; then
  python3 - "$CLAUDE_SETTINGS" "$builtin_rules" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]
rules_path = sys.argv[2]

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

with open(rules_path) as f:
    rules = json.load(f)

if "permissions" not in settings:
    settings["permissions"] = {}

removed = set(rules.get("removed", []))

existing_allow = set(settings["permissions"].get("allow", []))
repo_allow = set(rules.get("allow", []))
settings["permissions"]["allow"] = sorted((existing_allow | repo_allow) - removed)

existing_deny = set(settings["permissions"].get("deny", []))
repo_deny = set(rules.get("deny", []))
settings["permissions"]["deny"] = sorted((existing_deny | repo_deny) - removed)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

new_allow = repo_allow - existing_allow
new_deny = repo_deny - existing_deny
removed_count = len(removed & (existing_allow | existing_deny))

if new_allow or new_deny:
    print(f"  \033[32m✓\033[0m {len(new_allow)} allow + {len(new_deny)} deny rules added")
else:
    print(f"  \033[2m· All {len(repo_allow)} allow + {len(repo_deny)} deny rules already present\033[0m")

if removed_count:
    print(f"  \033[32m✓\033[0m {removed_count} retired rules removed")
PYEOF
else
  warn "$builtin_rules not found, skipping permissions merge"
fi

# --------------------------------------------------------------------------- #
# 4. Register MCP servers                                                     #
# --------------------------------------------------------------------------- #

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

_register_mcp "playwright" "@playwright/mcp" -- npx @playwright/mcp@latest

# --------------------------------------------------------------------------- #
# 5. Upsert <agent-skills-guidance> block in CLAUDE.md                        #
# --------------------------------------------------------------------------- #

section "Updating CLAUDE.md"

core_template="$SCRIPT_DIR/templates/user-claude.md"

if [[ -f "$core_template" ]]; then
  gh_user=""
  if command -v gh &>/dev/null; then
    gh_user="$(gh api user --jq .login 2>/dev/null || true)"
  fi

  block_content="$(cat "$core_template")"

  if [[ -n "$gh_user" ]] && [[ -f "$SCRIPT_DIR/templates/${gh_user}.md" ]]; then
    block_content="${block_content}

$(cat "$SCRIPT_DIR/templates/${gh_user}.md")"
    ok "Personal template for $gh_user"
  fi

  python3 - "$CLAUDE_MD" "$block_content" <<'PYEOF'
import sys
from pathlib import Path

claude_md_path = sys.argv[1]
new_content = sys.argv[2]

open_tag = "<agent-skills-guidance>"
close_tag = "</agent-skills-guidance>"

fenced_block = f"{open_tag}\n{new_content}\n{close_tag}"

claude_md = Path(claude_md_path)

if claude_md.exists():
    existing = claude_md.read_text()

    if open_tag in existing and close_tag in existing:
        before = existing[:existing.index(open_tag)]
        after = existing[existing.index(close_tag) + len(close_tag):]
        updated = before + fenced_block + after
        action = "Updated"
    elif open_tag in existing or close_tag in existing:
        print("  \033[33m⚠\033[0m Orphaned tag found — prepending fresh block")
        updated = fenced_block + "\n\n" + existing
        action = "Prepended"
    else:
        updated = fenced_block + "\n\n" + existing
        action = "Prepended"
else:
    updated = fenced_block + "\n"
    action = "Created"

claude_md.write_text(updated)
print(f"  \033[32m✓\033[0m {action} guidance block in {claude_md_path}")
PYEOF
else
  warn "$core_template not found, skipping CLAUDE.md update"
fi

# --------------------------------------------------------------------------- #
# Done                                                                        #
# --------------------------------------------------------------------------- #

printf "\n${_bold}${_green}✓ Setup complete${_reset}\n\n"
