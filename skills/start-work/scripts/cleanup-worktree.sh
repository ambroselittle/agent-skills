#!/usr/bin/env bash
# cleanup-worktree.sh — remove a git worktree and its branch.
#
# Usage:
#   cleanup-worktree.sh [<worktree-path|branch-name>] [--force] [--keep-branch]
#
# With no target, opens an fzf picker listing linked worktrees in the current
# repo (excludes the main worktree). Requires fzf.
#
# Verifies the worktree has no uncommitted changes and the branch is merged
# (into origin/<default> OR via a merged PR) before removing.
#
#   --force         Skip cleanliness + merge checks. Forces worktree remove
#                   and branch delete (-D).
#   --keep-branch   Remove the worktree only; leave the branch behind.

set -euo pipefail

force=false
keep_branch=false
target=""

for arg in "$@"; do
  case "$arg" in
    --force) force=true ;;
    --keep-branch) keep_branch=true ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \?//'
      exit 0 ;;
    -*)
      echo "Unknown flag: $arg" >&2
      exit 1 ;;
    *)
      if [[ -n "$target" ]]; then
        echo "Error: multiple targets given ('$target' and '$arg')" >&2
        exit 1
      fi
      target="$arg" ;;
  esac
done

# ----------------------------------------------------------------------------
# No target → fzf picker over linked worktrees in the current repo
# ----------------------------------------------------------------------------

if [[ -z "$target" ]]; then
  if ! command -v fzf &>/dev/null; then
    echo "Usage: $(basename "$0") [<worktree-path|branch-name>] [--force] [--keep-branch]" >&2
    echo "(Install fzf to pick interactively: brew install fzf)" >&2
    exit 1
  fi

  if ! cwd_top="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    echo "Error: no target given, and you're not inside a git repo." >&2
    echo "Run this from inside the source repo (or any worktree), or pass a path/branch." >&2
    exit 1
  fi

  git_common="$(git -C "$cwd_top" rev-parse --git-common-dir)"
  [[ "$git_common" != /* ]] && git_common="$cwd_top/$git_common"
  main_repo="$(cd "$(dirname "$git_common")" && pwd)"

  worktree_list="$(git -C "$main_repo" worktree list | awk -v main="$main_repo" '$1 != main')"
  if [[ -z "$worktree_list" ]]; then
    echo "No linked worktrees to clean up (only main repo at $main_repo)." >&2
    exit 1
  fi

  target="$(echo "$worktree_list" | fzf --height=40% --reverse --prompt="Cleanup worktree: " | awk '{print $1}')"
  if [[ -z "$target" ]]; then
    echo "No worktree selected." >&2
    exit 1
  fi
fi

# ----------------------------------------------------------------------------
# Resolve target → worktree_path, branch, source_repo
# ----------------------------------------------------------------------------

worktree_path=""
branch=""
source_repo=""

if [[ -d "$target" ]] && git -C "$target" rev-parse --is-inside-work-tree &>/dev/null; then
  worktree_path="$(cd "$target" && pwd)"
  git_common="$(git -C "$worktree_path" rev-parse --git-common-dir)"
  source_repo="$(cd "$(dirname "$git_common")" && pwd)"
  branch="$(git -C "$worktree_path" branch --show-current || true)"
else
  # Treat target as a branch name; find the worktree from the cwd's repo.
  branch="$target"
  if ! source_repo="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    echo "Error: '$target' is not a worktree path, and you're not inside a git repo." >&2
    echo "Run this from inside the source repo, or pass an absolute worktree path." >&2
    exit 1
  fi
  source_repo="$(cd "$source_repo" && pwd)"

  wt_path=""
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) wt_path="${line#worktree }" ;;
      "branch refs/heads/$branch")
        worktree_path="$wt_path" ;;
    esac
  done < <(git -C "$source_repo" worktree list --porcelain)

  if [[ -z "$worktree_path" ]]; then
    echo "Error: no worktree found for branch '$branch' in $source_repo." >&2
    exit 1
  fi
fi

if [[ "$worktree_path" == "$source_repo" ]]; then
  echo "Error: refusing to remove the main worktree at $source_repo." >&2
  exit 1
fi

if [[ -z "$branch" ]]; then
  echo "Error: worktree at $worktree_path is detached (no branch)." >&2
  echo "Use 'git worktree remove $worktree_path' manually." >&2
  exit 1
fi

echo "Worktree: $worktree_path"
echo "Branch:   $branch"
echo "Source:   $source_repo"
echo

# ----------------------------------------------------------------------------
# Safety checks (unless --force)
# ----------------------------------------------------------------------------

if [[ "$force" != "true" ]]; then
  # 1. No uncommitted changes
  if ! git -C "$worktree_path" diff --quiet || ! git -C "$worktree_path" diff --cached --quiet; then
    echo "Error: worktree has uncommitted changes." >&2
    echo "Commit/stash them, or pass --force." >&2
    exit 1
  fi

  # 2. Untracked files — prompt
  if [[ -n "$(git -C "$worktree_path" ls-files --others --exclude-standard)" ]]; then
    echo "Warning: worktree has untracked files."
    read -r -p "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
  fi

  # 3. Branch is merged — into origin/<default> OR via a merged PR
  default_base="$(git -C "$source_repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
    | sed 's|^origin/||' || echo main)"
  git -C "$source_repo" fetch origin "$default_base" --quiet 2>/dev/null || true

  merged=false
  if git -C "$source_repo" merge-base --is-ancestor "refs/heads/$branch" "origin/$default_base" 2>/dev/null; then
    merged=true
    echo "Branch is an ancestor of origin/$default_base."
  elif command -v gh &>/dev/null; then
    repo_slug="$(git -C "$source_repo" remote get-url origin | sed -E 's|.*github\.com[:/]||; s|\.git$||')"
    pr_state="$(gh -R "$repo_slug" pr list --head "$branch" --state all --json state --jq '.[0].state' 2>/dev/null || true)"
    if [[ "$pr_state" == "MERGED" ]]; then
      merged=true
      echo "PR for $branch is MERGED on GitHub."
    elif [[ -n "$pr_state" ]]; then
      echo "PR state: $pr_state (not MERGED)."
    fi
  fi

  if [[ "$merged" != "true" ]]; then
    echo "Error: branch '$branch' is not merged into origin/$default_base and has no merged PR." >&2
    echo "Pass --force to remove anyway." >&2
    exit 1
  fi
fi

# ----------------------------------------------------------------------------
# Remove worktree
# ----------------------------------------------------------------------------

if [[ "$force" == "true" ]]; then
  git -C "$source_repo" worktree remove --force "$worktree_path"
else
  git -C "$source_repo" worktree remove "$worktree_path"
fi
echo "✓ Worktree removed: $worktree_path"

# ----------------------------------------------------------------------------
# Delete branch
# ----------------------------------------------------------------------------

if [[ "$keep_branch" == "true" ]]; then
  echo "· Branch kept: $branch"
elif git -C "$source_repo" show-ref --verify --quiet "refs/heads/$branch"; then
  # Always -D: our own check above is the merge gate. git's -d uses a stricter
  # local-only definition that misses squash/rebase merges on GitHub.
  git -C "$source_repo" branch -D "$branch"
  echo "✓ Branch deleted: $branch"
fi

echo
echo "Done."
