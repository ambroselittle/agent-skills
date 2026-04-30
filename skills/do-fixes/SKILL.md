---
name: do-fixes
description: Apply fixes from a review. Detects the most recent review artifact and applies checked findings — currently supports code-review output. Verifies, commits, pushes, and posts the PR summary comment.
argument-hint: "[review-doc-path]"
depends-on: code-review
context: fork
---

# Do Fixes: Apply Review Findings

You are applying fixes from a completed review. This skill detects the most recent review artifact
and applies the appropriate fixes.

**Arguments:** $ARGUMENTS
- No arguments: auto-discover the most recent review doc for this branch
- Path: use the specified review doc

### Context Detection

Scan `.work/<slug>/reviews/` for the most recent review artifact:
- **`*.review.*.md`** (code-review output) → apply code fixes using the flow below
- *(Future: plan-review artifacts → apply plan improvements)*

The review document contains findings with checkboxes — checked `[x]` findings get fixed,
unchecked `[ ]` findings get skipped.

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Work folder: !`~/.claude/skills/shared/scripts/context.sh work-folder`
- Ticket ID: !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- HEAD SHA: !`~/.claude/skills/shared/scripts/context.sh head-sha`
- Open PR: !`~/.claude/skills/shared/scripts/context.sh open-pr`
- Uncommitted changes: !`~/.claude/skills/shared/scripts/context.sh uncommitted-changes`

**PR number:** extract from "Open PR" above (the number before the colon). Use this everywhere `<pr-number>` appears.

---

## Phase 0: Orient

### Find the review document

If a path was provided as argument, use it. Otherwise, auto-discover:

1. Use the pre-loaded `Work folder`. If "none", fall back to `.work/general/reviews/`.
2. Look in `<work-folder>/reviews/` for review files (`*.review.*.md`).
3. Use the most recent one (by date in filename).
4. If no review doc found in the work folder, fall back to `.work/general/reviews/`.

If still no review doc: "No review document found. Run `/code-review` first to generate one."

### Read the review document

Read the review doc. Note:
- The `phase:` in frontmatter — if already `committed` or `fixes-verified`, warn: "This review has already been applied. Run `/code-review full` for a new review cycle."
- The checked `[x]` findings — these are the ones to fix
- Any `**Instructions:**` fields — user instructions take priority over reviewer suggestions
- The `sha:` — the HEAD at review time

### Read project context

Read `CLAUDE.md` at the repo root — note verification commands (lint, typecheck, test, format) for use in Phase 1.

### Check for uncommitted changes

If there are uncommitted changes (from pre-loaded context): "There are uncommitted changes. Want to stash them before proceeding, or continue as-is?" Wait for their answer.

**Create progress tasks:**

1. Fix findings
2. Verify fixes
3. Finalize — update review doc, commit, push
4. Post PR summary comment

Update the review doc's `phase:` to `fixes-in-progress`.

---

## Phase 1: Fix

### Step 1: Group findings into fix batches

Findings touching the same file(s) MUST be in the same batch (prevents edit conflicts). Non-overlapping batches can run as parallel agents. Each batch: 1-5 findings.

### Step 2: Regression tests (BLOCKER/ISSUE only)

Write tests that **prove the bug exists** before fixing it. Scope: only unit-testable BLOCKER/ISSUE findings. Skip: cache behavior, convention fixes, dead code, styling. SUGGESTIONs and NITs never need tests.

1. Farm out test writing to parallel agents. Each agent:
   - Receives the finding text and relevant source file content
   - Instruction: write a **focused test that fails against current code** — do NOT fix the code
   - **EDITS ONLY** — no running tests
   - **Budget: 3 edit rounds**
2. Run all new tests centrally — they should **fail** (proving the bug exists).
3. If a test passes (doesn't prove the bug): retry up to 3x with a fresh agent. After 3 failures, mark: `Regression test: could not write a proof test for F<n>, proceeding without`.

### Step 3: Farm out edits to agents

**YOU (the coordinator) do NOT make edits. Delegate ALL edits to agents.**

**Maximize parallelism.** Look at the batches from Step 1. All batches that touch non-overlapping files can (and should) be spawned as parallel agents simultaneously — a single message with multiple Agent tool calls, not sequential spawns. Only serialize batches that share files. For a typical review with 3-7 findings across different files, most or all batches should run in parallel.

Each agent receives:
- The specific finding(s) to address (full finding text including user Instructions)
- Relevant file content (read and pass — don't assume agents can find things)
- Clear acceptance criteria
- **User instructions** from `**Instructions:**` field take priority over reviewer suggestions
- Instruction to follow all CLAUDE.md guidelines
- **EDITS ONLY — no running tests, typecheck, lint, format, starting any processes, or committing.** The coordinator runs verification after all agents complete. Parallel agents each spinning up their own processes will thrash the machine.
- **Budget: 5 edit rounds**

If an agent discovers a finding is incorrect (e.g., would break types, code is actually fine): agent skips and reports why. Mark with a note rather than forcing a bad change.

### Step 4: Track progress

Read `~/.claude/skills/shared/references/finding-format.md` for the status lifecycle. Update the review doc as agents report back:
- `[x]` -> `[fixed]` after editing, with one-line change summary
- `[fixed]` -> `[verified]` after verification passes (batch-update)
- If verification fails, leave as `[fixed]` and append what failed
- `[ ]` -> `[skipped]` for unchecked findings

### Step 5: Verify (centrally, after ALL edits complete)

**Do not run verification until all edit agents have reported back.**

**CRITICAL: Verification is mandatory before any commit or push. No exceptions, no shortcuts.**

1. **Read CLAUDE.md and `.claude/rules/`** to find the repo's verification commands and policies.
   If a `verification.md` rule exists, follow it exactly — it may require running the full test
   suite, not just targeted tests.
2. **Format** changed files only (runs first — it modifies files):
   - Get changed files: `git diff $(git merge-base HEAD main)...HEAD --name-only`
   - Use repo-appropriate formatter from CLAUDE.md
3. **Run the repo's verification suite.** Follow whatever CLAUDE.md or `.claude/rules/verification.md`
   specifies. If neither prescribes a scope, default to:
   - Typecheck (full — types are global)
   - Tests related to changes (filename pattern filters)
   If the repo's rules say to run the full suite, run the full suite.
4. **All checks must pass.** If verification fails, fix the issue and re-verify. Do not commit
   or push with failing checks. If you cannot fix a failure after 2 attempts, stop and report
   to the user.

If verification fails, fix issues (spawn new agents if needed), then re-verify.

### Step 6: Resolve all findings

Before committing, scan the review document and ensure every checked `[x]` finding has been updated to a terminal status. No finding should still show bare `[x]` at this point.

Terminal statuses: `[fixed]` -> `[verified]`, `[skipped]`, `[will-not-do]`, `[deferred]`, `[already-resolved]`, `[could-not-prove]`.

If any checked findings are still `[x]`: update them now — mark `[skipped]` with a note if they were intentionally not addressed, or `[deferred]` if out of scope.

---

## Phase 2: Finalize

**The full sequence is: verify -> commit -> push -> post PR comment. All four steps are mandatory
and must happen in order. Do not skip any step. Do not push without verifying. Do not end the
session without posting the PR comment.**

**Auto-proceed:** Once fixes are complete and verification passes, immediately continue through
all of Phase 2 — commit, push, then post the PR comment — without stopping to ask. The user
invoked this skill to apply fixes; that authorizes the full cycle through commit, push, and
publish. Only pause if: (a) verification still fails after fix attempts, (b) a finding requires
a judgment call not covered by the user's instructions, or (c) an unanswered question came up
that needs a decision before proceeding.

### Step 7: Commit

Update review doc `phase:` to `fixes-verified`. **All fixes for a review cycle go into a single commit** — never split by finding. Update `phase:` to `committed`.

### Step 8: Push + update PR checklist

Push the branch:
```bash
git push
```

**Mark code review complete on the PR.** Read the PR body:
```bash
gh pr view <pr-number> --json body -q .body
```
- If it contains an unchecked `- [ ] Ran \`/code-review\`` item, check it off (`- [x]`)
- If it has no such item, append `- [x] Ran \`/code-review\`` to the checklist section (or the end of the body if no checklist exists)

Update with `gh pr edit <pr-number> --body "<updated-body>"`.

### Step 9: Post the PR comment — THIS STEP IS MANDATORY. DO NOT SKIP.

**You have just finished a code review cycle. The team cannot see the outcome unless you post this comment. It is the only artifact that surfaces the review on the PR. Do it now.**

First, re-read the review document from disk — your in-context copy may be stale after parallel fix agents updated it:
```bash
cat .work/<ticket>/reviews/<review-filename>.md
```

Then spawn a sub-agent (`model: sonnet`) with the following:

> "Read `~/.claude/skills/shared/references/code-review-summary-format.md` for the exact comment format — follow it precisely, do not invent a different layout.
>
> Post or update a PR comment summarizing this code review cycle.
>
> **PR number:** <pr-number>
> **Fix commit SHA:** <sha> (omit the fix commit link if no fixes were made)
> **Review SHA:** <7-char short SHA from the review doc filename>
> **Review doc contents:**
> <paste full contents of the review doc as just read from disk>
>
> **Human feedback suppression:** if the review doc contains a `## Human Feedback Cross-Reference`
> section listing dropped findings, include the suppression line after the findings table per the
> format reference: `> N findings suppressed — already raised by PR reviewers` (where N is the
> count of dropped findings). Omit this line if N = 0. Do NOT include the cross-reference table
> itself in the PR comment.
>
> **Comment identity:** each review round gets its own comment, keyed by a `<!-- code-review: <review-sha> -->` marker (the SHA from the review doc filename, not the fix commit).
> 1. Search existing PR comments for a marker matching this review SHA: `gh api repos/<owner>/<repo>/issues/<pr-number>/comments --jq '.[] | select(.body | contains("<!-- code-review: <review-sha> -->")) | .id'`
> 2. If found -> update that comment with `gh api repos/<owner>/<repo>/issues/comments/<id> -X PATCH --field body="<formatted>"` (this is a resumed partial post)
> 3. If not found -> post a new comment with `gh pr comment <pr-number> --body "<formatted>"`
>
> Extract the comment ID from the gh output (the numeric ID at the end of the comment URL, e.g. `4155206998` from `...#issuecomment-4155206998`) and return it."

If no PR exists, skip this step — the review doc stays local.

---

## Phase 3: Retrospective

After the fixes are complete:
1. **Ensure the PR comment is current.** Check whether a PR summary comment has been posted covering this review cycle. If a comment was posted but findings changed after it (e.g., additional fixes were pushed), post an updated comment using the Step 9 sub-agent.
2. Summarize what was found, fixed, and deferred.
3. Ask the user if any review agents or the code-review skill should be updated based on what was missed or noisy.
4. With user approval, suggest edits to the relevant `.claude/agents/reviewers/` files.

**Next step:** If the PR has reviewer feedback to address, handle it before merging. Otherwise, merge the PR.

---

## Agent Budgets

Agents can get stuck. Include budget instructions in every agent prompt.

| Agent type             | Budget         | On budget hit                                    |
|------------------------|----------------|--------------------------------------------------|
| Regression test writer | 3 edit rounds  | Report back with best attempt + what's blocking  |
| Fix agent              | 5 edit rounds  | Report back with partial progress + what's stuck |
| Retry agent            | 2 edit rounds  | Flag as "could not prove" and move on            |

**Include in every agent prompt:** "You have a budget of N edit rounds. If you haven't succeeded after N edits to the same file, stop and report back with what you've tried and what's blocking you. Do not keep retrying the same approach."

When an agent hits budget: (1) accept partial work if close enough, (2) spawn fresh agent with different instructions, or (3) escalate to user. Max 2 fresh-agent retries per finding before escalating.

---

## Important Guidelines

- **YOUR JOB IS CONTEXT.** Ensure each agent has everything it needs. Don't assume agents can find project conventions — pass them the relevant content.
- **Speed is not the goal.** Correctness and verifiability are.
- **When stuck, STOP and ask.** If you or any agent is spinning, escalate to the user immediately.
- **Session continuity:** Before ending, ensure the review document is saved with current `phase:` and findings state.

### Non-Negotiable Invariants

These are hard requirements. Violating any of them is a bug in execution, not a judgment call.

1. **Verify before pushing.** Run the repo's full verification suite (from CLAUDE.md / `.claude/rules/verification.md`) and confirm all checks pass before any `git push`. A push without green checks wastes CI and the reviewer's time.
2. **PR comment after pushing.** Every push that includes review fixes MUST be followed by a PR summary comment (Phase 2 Step 9). The PR comment is the only artifact that surfaces the review outcome to the team. If the session ends without it, the review is invisible.
3. **PR comment is keyed by review SHA.** Each review round gets its own comment, keyed by a `<!-- code-review: <review-sha> -->` marker (the SHA from the review doc filename). Phase 2 Step 9 handles this in the formal fix flow. Phase 3 is the catch-all. The comment must exist and be current before the session ends.
