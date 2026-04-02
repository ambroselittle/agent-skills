#!/bin/bash
# Pre-loaded context helper for code-review skill.
# Usage: context.sh <flag>
case "$1" in
  ci-status)
    if [ "$CI" = "true" ]; then echo "YES"; else echo "no"; fi
    ;;
  reviewer-agents)
    # Merge repo agents + built-in agents into a single pool.
    # Repo agents override built-ins of the same name.
    # Agents with `always: true` frontmatter are always included; others are coordinator-selectable.
    _skill_dir="$(cd "$(dirname "$0")/.." && pwd)"
    _builtin_dir="$_skill_dir/agents"
    _repo_dir=".claude/agents/reviewers"

    _all_names=$(
      { ls "$_builtin_dir"/*.md 2>/dev/null; ls "$_repo_dir"/*.md 2>/dev/null; } \
        | xargs -I{} basename {} .md | sort -u
    )

    _always="" _selectable=""
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if   [[ -f "$_repo_dir/$name.md" ]];    then f="$_repo_dir/$name.md"
      elif [[ -f "$_builtin_dir/$name.md" ]]; then f="$_builtin_dir/$name.md"
      else continue; fi
      if grep -q "^always: true" "$f" 2>/dev/null; then
        _always="$_always $name"
      else
        _selectable="$_selectable $name"
      fi
    done <<< "$_all_names"

    printf "always-on: %s\n"   "$(echo $_always    | xargs)"
    printf "selectable: %s\n"  "$(echo $_selectable | xargs)"
    ;;
  work-plan)
    find .work -maxdepth 2 -name plan.md 2>/dev/null | head -1 | xargs head -30 2>/dev/null
    ;;
  reversed-diff)
    # Produce a git diff with file order reversed for pass-2 seeding.
    # Splits on "diff --git" boundaries, reverses the file blocks, rejoins.
    # Works with both PR diffs and local diffs against origin/main.
    # Optional: --pr <num> to pass a known PR number (avoids re-querying).
    # Optional: pass file paths as trailing args to scope the diff (for incremental reviews).
    shift  # consume "reversed-diff"
    _pr_num=""
    if [[ "$1" == "--pr" && -n "$2" ]]; then
      _pr_num="$2"; shift 2
    fi
    _files=("$@")

    # Resolve PR number if not provided
    if [[ -z "$_pr_num" ]]; then
      _pr_num=$(gh pr view --json number -q .number 2>/dev/null)
    fi

    if [[ -n "$_pr_num" ]]; then
      # gh pr diff does not accept path args — always get full diff, filter after
      _raw_diff=$(gh pr diff "$_pr_num" 2>/dev/null)
    else
      git fetch origin main -q 2>/dev/null || true
      _raw_diff=$(git diff "$(git merge-base HEAD origin/main)...HEAD" 2>/dev/null)
    fi

    # Filter to specific files if requested
    if [[ ${#_files[@]} -gt 0 && -n "$_raw_diff" ]]; then
      _filter_pattern=$(printf "|%s" "${_files[@]}")
      _filter_pattern="${_filter_pattern:1}"  # strip leading |
      _raw_diff=$(echo "$_raw_diff" | awk -v pat="$_filter_pattern" '
        BEGIN { split(pat, files, "|"); for (i in files) wanted[files[i]] = 1 }
        /^diff --git / {
          if (block != "" && keep) out = out block
          block = $0 "\n"; keep = 0
          # extract b-side path: diff --git a/X b/X
          n = split($0, parts, " "); path = parts[n]; sub(/^b\//, "", path)
          if (path in wanted) keep = 1
          next
        }
        { block = block $0 "\n" }
        END { if (block != "" && keep) out = out block; printf "%s", out }
      ')
    fi
    if [[ -z "$_raw_diff" ]]; then
      echo ""
    else
      echo "$_raw_diff" | awk '
        /^diff --git / {
          if (block != "") { blocks[n++] = block }
          block = $0 "\n"
          next
        }
        # awk strips the record separator from $0, so newlines are added explicitly
        { block = block $0 "\n" }
        END {
          if (block != "") blocks[n++] = block
          for (i = n-1; i >= 0; i--) printf "%s", blocks[i]
        }
      '
    fi
    ;;
  *)
    echo "unknown flag: $1" >&2; exit 1
    ;;
esac
