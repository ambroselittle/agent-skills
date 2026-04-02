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
    # Override: create ~/.claude/user-slug with your preferred slug.
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
  plans-in-progress)
    # Space-separated list of active work slugs (excludes done/), e.g. "issue-42-foo issue-99-bar".
    find .work -maxdepth 3 -name plan.md 2>/dev/null | sed 's|/plan.md$||' | sed 's|^\.work/||' | grep -v '^done' | tr '\n' ' ' || echo "failed to discover"
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
