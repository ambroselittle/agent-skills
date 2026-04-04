#!/bin/bash
# get-diff.sh — get the full diff for a branch, preferring PR diff over local.
#
# Usage: get-diff.sh [--name-only] [--branch <branch>]
#
# Prefers `gh pr diff` if an open PR exists for the branch.
# Falls back to `git diff $(git merge-base HEAD origin/main)...HEAD`.
# --branch: target branch (defaults to current branch)
# --name-only: output file names only

set -euo pipefail

NAME_ONLY=""
BRANCH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name-only) NAME_ONLY="--name-only"; shift ;;
    --branch)    BRANCH="$2"; shift 2 ;;
    *)           echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Resolve PR for the given branch (or current branch)
if [[ -n "$BRANCH" ]]; then
  PR_NUMBER=$(gh pr view "$BRANCH" --json number --jq '.number' 2>/dev/null || true)
else
  PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || true)
fi

if [[ -n "$PR_NUMBER" ]]; then
  gh pr diff "$PR_NUMBER" $NAME_ONLY
else
  git fetch origin main -q 2>/dev/null || true
  git diff $(git merge-base HEAD origin/main)...HEAD $NAME_ONLY
fi
