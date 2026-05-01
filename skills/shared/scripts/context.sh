#!/bin/bash
# Shared pre-loaded context helper for engineering skills.
# Usage: context.sh <flag>
case "$1" in
  current-branch)
    # The current git branch name, or "not in a git repo" if outside a repo.
    git branch --show-current 2>/dev/null || echo "not in a git repo"
    ;;
  open-pr)
    # The open PR for the current branch as "#number: title — url", or "none" if none.
    _pr_json=$(gh pr view --json number,url,title 2>/dev/null) && \
      echo "$_pr_json" | jq -r '"\(.number): \(.title) — \(.url)"' 2>/dev/null || echo "none"
    ;;
  user-slug)
    # The engineer's personal slug (used for branch prefixes), e.g. "ambrose".
    # Priority: ~/.claude/agent-skills.json user_prefix → ~/.claude/user-slug → git user.name
    _config="$HOME/.claude/agent-skills.json"
    if [ -f "$_config" ]; then
      _prefix=$(python3 -c "
import json, sys
try:
  d = json.load(open('$_config'))
  p = d.get('user_prefix', '')
  if p: print(p)
except: pass
" 2>/dev/null)
      [ -n "$_prefix" ] && echo "$_prefix" && exit 0
    fi
    if [ -f ~/.claude/user-slug ]; then
      cat ~/.claude/user-slug
    else
      git config user.name 2>/dev/null | tr '[:upper:]' '[:lower:]' | awk '{print $1}' || echo "unknown"
    fi
    ;;
  repo-remote)
    # The GitHub owner/repo for the current repo, e.g. "ambroselittle/some-project".
    _remote=$(git remote get-url origin 2>/dev/null) && \
      echo "$_remote" | sed 's|.*github\.com[:/]\(.*\)\.git$|\1|' | sed 's|.*github\.com[:/]\(.*\)$|\1|' || echo "unknown"
    ;;
  uncommitted-changes)
    # Short git status (first 20 lines), or "clean" if nothing to report.
    _status=$(git status --short 2>/dev/null | head -20)
    [ -n "$_status" ] && echo "$_status" || echo "clean"
    ;;
  head-sha)
    # Short SHA of HEAD commit.
    git rev-parse --short HEAD 2>/dev/null || echo "unknown"
    ;;
  recent-commits)
    # Last 5 commits, one line each.
    git log --oneline -5 2>/dev/null || echo "no commits"
    ;;
  work-folder)
    # Resolves the work folder for the current branch using ~/.claude/agent-skills.json.
    # Returns: needs-setup | none | <absolute-path>
    # "needs-setup" means no config exists. "none" means on main/master.
    # Otherwise returns the path (existing directory or derived path for new plans).
    _config="$HOME/.claude/agent-skills.json"
    if [ ! -f "$_config" ]; then echo "needs-setup"; exit 0; fi
    _work_root=$(python3 -c "
import json, os, sys
try:
  d = json.load(open('$_config'))
  r = d.get('work_root', '')
  print(os.path.expanduser(r) if r else '')
except: pass
" 2>/dev/null)
    if [ -z "$_work_root" ]; then echo "needs-setup"; exit 0; fi
    _branch=$(git branch --show-current 2>/dev/null)
    case "$_branch" in main|master|"") echo "none"; exit 0 ;; esac
    _slug="${_branch#*/}"
    _token=$(echo "$_slug" | grep -oiE '[a-z]+-[0-9]+' | head -1)
    _found=""
    if [ -n "$_token" ] && [ -d "$_work_root" ]; then
      _found=$(find "$_work_root" -maxdepth 1 -type d -iname "${_token}-*" 2>/dev/null | sort | head -1)
      [ -z "$_found" ] && _found=$(find "$_work_root" -maxdepth 1 -type d -iname "${_token}" 2>/dev/null | head -1)
    fi
    if [ -z "$_found" ] && [ -d "$_work_root" ]; then
      _found=$(find "$_work_root" -maxdepth 1 -type d -name "$_slug" 2>/dev/null | head -1)
    fi
    # Return found dir or derived path (caller checks if plan.md exists within it)
    [ -n "$_found" ] && echo "$_found" || echo "$_work_root/$_slug"
    ;;
  ticket-id)
    # Extracts the ticket ID from the current branch name (e.g. "ENG-42"), or "none".
    # Strips user prefix, then matches [a-z]+-[0-9]+ pattern (uppercased on output).
    _branch=$(git branch --show-current 2>/dev/null)
    _slug="${_branch#*/}"
    _ticket=$(echo "$_slug" | grep -oiE '[a-z]+-[0-9]+' | head -1 | tr '[:lower:]' '[:upper:]')
    [ -n "$_ticket" ] && echo "$_ticket" || echo "none"
    ;;
  plans-in-progress)
    # Lists active work slugs from the configured work_root, e.g. "eng-42-foo eng-99-bar".
    _config="$HOME/.claude/agent-skills.json"
    _work_root=$(python3 -c "
import json, os, sys
try:
  d = json.load(open('$_config'))
  r = d.get('work_root', '')
  print(os.path.expanduser(r) if r else '')
except: pass
" 2>/dev/null)
    if [ -z "$_work_root" ] || [ ! -d "$_work_root" ]; then echo "none"; exit 0; fi
    find "$_work_root" -maxdepth 2 -name plan.md 2>/dev/null \
      | sed "s|$_work_root/||" | sed 's|/plan.md$||' | grep -v '^done' | tr '\n' ' ' || echo "none"
    ;;
  unpushed)
    # Commits ahead of the upstream tracking branch (up to 10).
    git log --oneline "@{u}.." 2>/dev/null | head -10
    ;;
  pr-template)
    # Whether a PR template exists: "found" or "none".
    if [ -f .github/pull_request_template.md ]; then echo "found"; else echo "none"; fi
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
