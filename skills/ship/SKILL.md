---
name: ship
description:
  Commit any uncommitted task work, push your branch, and open a PR. Use this
  when you're done with your changes and ready to share them — say "ship", "ship
  it", or "let's ship". If there are uncommitted changes, verifies and commits
  them first. Opens a PR using the repo's template. After shipping, run
  /code-review on the PR.
argument-hint: "[pr-title]"
---

# Ship: Push and Open a PR

You are getting finished work across the line.

**Arguments:** $ARGUMENTS (optional PR title override)

**Pre-loaded context:**

- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Uncommitted changes: !`~/.claude/skills/shared/scripts/context.sh uncommitted-changes`
- Unpushed commits: !`~/.claude/skills/ship/scripts/context.sh unpushed`
- Open PR: !`~/.claude/skills/shared/scripts/context.sh open-pr`
- PR template: !`~/.claude/skills/ship/scripts/context.sh pr-template`

---

## Step 1: Assess State

If on `main` or `master`: stop — "You're on `main`. Switch to a feature branch
first."

Determine what's needed based on pre-loaded context:

| State                                          | Action                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------- |
| Open PR, nothing uncommitted, nothing unpushed | "Already shipped — PR is open at [url]. Want me to run `/code-review` now?" |
| Open PR, unpushed commits                      | Push, then done                                                      |
| Open PR, uncommitted changes                   | Verify → commit → push                                               |
| No PR, commits ready                           | Push → open PR                                                       |
| No PR, uncommitted changes                     | Verify → commit → push → open PR                                     |

---

## Step 2: Verify + Commit (only if uncommitted changes)

If there are no uncommitted changes, skip to Step 3.

**Verify first:**

1. Get changed files: `git diff --name-only`
2. Format changed files using the repo's formatter (from `CLAUDE.md`)
3. Run typecheck and tests in parallel

If verification fails: fix the issue, re-run once. If still failing, stop —
don't ship broken code.

**Commit:**

- Review `git status` carefully — stage only files that belong to this change.
  Watch for stray generated files, lock file noise, or `.env` changes.
- Write a commit message following the repo's style (check
  `git log --oneline -5`).
- Present: "Committing: `<message>`" and commit on approval.

---

## Step 3: Docs Sanity Check

Spawn the **devdocs reviewer agent** on the full diff:

```bash
bash ~/.claude/skills/shared/scripts/get-diff.sh
```

Pass it the diff and instruct it to identify any stale or missing docs — READMEs, rule files, templates, skill definitions, inline comments.

Read the devdocs agent definition from `~/.claude/skills/code-review/agents/devdocs.md` and use it as the agent's persona and instructions.

If the agent finds anything: surface it to the user — "Before I push, the docs reviewer flagged: [findings]. Want me to fix these first?" Wait for their call. If nothing: proceed silently.

---

## Step 4: Push

`git push -u origin <branch>`

---

## Step 5: Pull Request

**PR already open**: done — "Pushed to [url]. Ready for `/code-review`."

**No PR**: create one now.

Read the PR template if one was found (pre-loaded). Fill it out fully — use
`[n/a]` for inapplicable checklist items, never omit them.

Derive the PR body from:

- The plan at `.work/<slug>/plan.md` if it exists (goal, scope, phases completed)
- `git log --oneline @{u}..` for the commit history

**Write the PR body as capabilities, not a file inventory.** Describe what the PR enables or changes from a user/engineer perspective — new behaviors, fixed problems, improved workflows. Group by feature or theme. Do NOT list files changed and what each file does; that's what `git diff` is for. One exception: call out a specific file if it's the primary interface point (e.g., "Edit `servers.json` to add a new server").

**Key Decisions section.** If a plan exists, read its `## Context`, `## Lessons`, and `## Open Questions` sections. Synthesize a "Key Decisions" section for the PR body that captures:
- Important technical choices made during implementation and their rationale
- Alternatives that were considered and why they were rejected
- Any scope decisions (what was intentionally left out and why)

Keep this section concise — 3–5 bullets max. If there are no meaningful decisions to highlight (trivial change), omit the section.

Present the draft title and body for confirmation, then:
`gh pr create --title "<title>" --body "<body>"`

Share the URL and prompt for code review: "PR open at [url]. Run `/code-review` to review it."

Update the plan if one exists: find `.work/<slug>/plan.md` by matching the branch name, then update the frontmatter `status: pr-open` and add a `pr:` field with the PR URL. This keeps the plan current so `/code-review` can find it.

---

## Step 6: Learn Nudge

If a plan exists at `.work/<slug>/plan.md`, check its `## Lessons` section. If it has bullet entries (not just the comment placeholder):

> "There are lessons captured in this work item's plan. Want to run `/learn` to route them?"

If no lessons or no plan: skip silently.

---

## Guidelines

- **Never push to main/master directly.**
- **Stray files are your responsibility.** Review `git status` before staging.
- **The PR template is a contract.** If the repo has one, fill it out.
- **If verification fails, don't ship.** Broken CI wastes everyone's time.
