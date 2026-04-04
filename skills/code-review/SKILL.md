---
name: code-review
description: Review a pull request with multi-pass parallel specialized agents. Run after opening a PR, or before one exists to diff against main. Merges repo-specific reviewers (`.claude/agents/reviewers/`) with built-in reviewers — repo overrides built-in on name collision. Always-on agents (security, devdocs) run regardless of diff. Default is incremental (commits since last review); use `full` for the entire PR.
argument-hint: "[full | pr-url]"
context: fork
---

# Code Review: Multi-Agent Code Review

You are the coordinator of a parallel code review team.

**Arguments:** $ARGUMENTS
- No arguments: incremental — review commits since the last review (reads SHA from `.work/<ticket>/reviews/` filenames); if no prior review, uses full PR diff
- `full`: entire PR diff regardless of prior reviews
- PR URL: review a specific PR

**Current state (pre-loaded):**
- CI environment: !`~/.claude/skills/code-review/scripts/context.sh ci-status`
- HEAD SHA: !`~/.claude/skills/shared/scripts/context.sh head-sha`
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Open PR: !`~/.claude/skills/shared/scripts/context.sh open-pr`
- Recent commits: !`~/.claude/skills/shared/scripts/context.sh recent-commits`
- Reviewer agents found: !`~/.claude/skills/code-review/scripts/context.sh reviewer-agents`
- Work plan: !`~/.claude/skills/code-review/scripts/context.sh work-plan`

**PR number:** extract from "Open PR" above (the number before the colon). Use this everywhere `<pr-number>` appears — do not re-query with `gh pr view` to get the PR number.

**CI check:** If "CI environment" above shows `YES`, stop immediately and respond:
> "/code-review is not yet supported in CI environments — it requires interactive input.
> Run it locally before pushing instead."

---

## Phase 1: Orientation

1. **Read project context.** Read `CLAUDE.md` at the repo root — note verification commands (lint, typecheck, test), conventions, and any areas of special concern. Note the verification commands for use in Phase 4.

   **Model check.** If you are not running on Opus, emit this note before continuing:
   > For best synthesis quality, switch to Opus with: `/model opus` (no restart needed)

   Then continue regardless — this is advisory only.

2. **Determine review scope.**

   Find current ticket by matching branch name against `.work/` subdirectory names. If no match, use `.work/general/reviews/`.

   **Diff source — prefer PR diff over local diff:**

   - **PR exists** (pre-loaded above shows an open PR, or a PR URL was passed as argument):
     - **Incremental** (default): find the most recent review file in `.work/<ticket>/reviews/` by SHA suffix (`YYYY-MM-DD-<sha>.md`). Run `gh pr diff <pr-number> -- $(git log <sha>...HEAD --name-only | sort -u | tr '\n' ' ')` to scope to changed files since last review. If filtering is too complex, use full PR diff with a note.
     - **Full** (`full` argument or no prior review): run `gh pr diff <pr-number>`.

   - **No PR yet** (pre-loaded shows no open PR):
     - Run `git fetch origin main` first to ensure main is current, then `git diff $(git merge-base HEAD origin/main)...HEAD`.
     - Note to user: "No open PR found — diffing against origin/main. Results may include drift if main has moved significantly since you branched."

3. **Read the diff.** First run `gh pr diff --name-only` (or `git diff --name-only $(git merge-base HEAD origin/main)...HEAD` if no PR) to get a file list. Then read the full diff. For large diffs (>500 lines), read each changed file individually rather than the full diff at once.

4. **Fetch existing PR feedback** (skip if no PR exists).

   Get the PR author login and resolve the repo slug:
   ```bash
   gh pr view <pr-number> --json author -q .author.login
   ```

   Fetch all three feedback channels **in parallel** (three Bash tool calls in a single message —
   they are independent):
   ```bash
   gh api repos/<owner>/<repo>/pulls/<pr-number>/comments --paginate
   gh api repos/<owner>/<repo>/pulls/<pr-number>/reviews --paginate
   gh api repos/<owner>/<repo>/issues/<pr-number>/comments --paginate
   ```

   Resolve `<owner>/<repo>` from the git remote (same approach as Phase 4 Step 9).

   **Build the Existing Feedback Digest** — a coordinator-internal summary of what humans have
   already said on this PR. This is NOT passed to reviewer agents — they must stay unbiased.

   - **Filter out:** comments from the code-review bot (body contains `<!-- code-review:`),
     pure approval reviews with empty body, LGTM/praise-only comments, bot/CI comments
   - **Group inline comments into threads** using `in_reply_to_id`. Comments with
     `in_reply_to_id: null` are thread roots (the concern). Comments referencing a parent ID
     are replies (the conversation).
   - **For each thread, classify the resolution signal** based on whether the PR author
     (from the login fetched above) or other participants replied:
     - `intentional` — author explained the behavior is deliberate
     - `acknowledged` — author agreed or said they'll fix it
     - `already-fixed` — author says it's been fixed
     - `disputed` — author pushed back, no consensus reached
     - `no-response` — no author reply in the thread
   - **Extract review-level concerns** from reviews with non-empty body (especially
     CHANGES_REQUESTED reviews — these carry the most weight).
   - **Extract substantive issue comments** — skip procedural comments.
   - **Keep the digest compact:** for each thread, extract the core concern (one line) and
     resolution signal with a brief quote from the response. Do not include full comment bodies.
   - **High-volume PRs (50+ inline comment threads):** focus on the most recent review round
     (filter by `created_at` or `submitted_at`) and CHANGES_REQUESTED reviews. Older resolved
     threads are less likely to collide with new findings. Summarize older rounds as a count
     ("N older threads omitted — all resolved") rather than listing each one.

   Hold this digest for use in Phase 3. Example format:

   ```
   ## Existing Feedback Digest

   ### Inline Threads

   E1. @alice — src/parser.ts:L42 — "Missing null check on config param"
       Resolution: intentional — author: "X upstream guarantees non-null here"

   E2. @bob — src/api.ts:L88 — "Timeout should be configurable"
       Resolution: acknowledged — author: "Good catch, will fix"

   E3. @alice — src/utils.ts:L15 — "Consider extracting this to a shared helper"
       Resolution: no-response

   ### Review-Level Concerns

   E4. @carol (CHANGES_REQUESTED) — "Error handling in the new parser needs work"
       Resolution: no-response
   ```

5. **Select reviewers.** Use the pre-loaded list above, which shows two groups:

   - **always-on**: run unconditionally — no exceptions, no skipping based on diff size or relevance.
   - **selectable**: coordinator decides which to include. Include an agent if there is any material
     overlap between its domain and the diff. When in doubt, include it — a small diff just means
     fewer findings, not wasted effort. Repo agents with the same name as a built-in automatically
     override the built-in (context.sh handles the merge; you just use the list as given).

   Tell the user which reviewers you're running and why, then proceed without waiting:
   ```
   Running reviewers: security [always], devdocs [always], configure, pre-tool-use-hook, testing
   (skipping: architecture — no new patterns, abstractions, or component interfaces in this diff)
   ```

---

## Phase 2: Review (Two-Pass Parallel — Read-Only)

> **Why two passes?** SWR-Bench multi-review research shows that running each reviewer twice with
> diff-order shuffling between passes, then aggregating findings, yields +118% recall vs a single
> pass. Repetition alone (same diff twice) has no effect (p=0.11) — the gain comes from seeded
> variation plus cross-pass aggregation. Pass 2 presents files in reverse order to reduce
> position-dependent blind spots (K-LLM approach).

**Create review cycle tasks** — at the start of each review cycle, create the following tasks to
track progress. Mark each `in_progress` when you start it, `completed` when done. In full auto
mode, mark tasks 2 and 3 completed immediately without stopping.

1. Run review
2. Present findings *(skip in full auto — mark completed immediately)*
3. Get user input *(skip in full auto — mark completed immediately)*
4. Fix findings
5. Verify fixes
6. Finalize — update review doc, commit, push
7. Post PR summary comment

Run each selected reviewer **twice in parallel** — pass 1 with the normal diff, pass 2 with the
reversed diff. No edits in this phase.

**Get the reversed diff for pass 2** — pass `--pr <pr-number>` (the number extracted earlier) and the same file list used for pass 1 to keep scope consistent (incremental reviews scope to changed files since last review; full reviews omit the file list):
```bash
# Incremental: bash ~/.claude/skills/code-review/scripts/context.sh reversed-diff --pr <pr-number> <file1> <file2> ...
# Full PR:     bash ~/.claude/skills/code-review/scripts/context.sh reversed-diff --pr <pr-number>
```

Read `${CLAUDE_SKILL_DIR}/references/finding-format.md` and `${CLAUDE_SKILL_DIR}/references/review-discipline.md` — include the full content of both in every agent prompt.

**Collect applicable repo rules** (once, before spawning any agents):
1. List all files in `.claude/rules/`. If the directory doesn't exist or is empty, skip this step.
2. For each rule file, read its `paths:` frontmatter. If any glob matches a file in the diff, mark it as diff-applicable — include its content for all agents.
3. For each reviewer `<name>`, check if `.claude/rules/<name>.md` exists — if so, include its content for that reviewer specifically.
4. Pass to each agent: content of diff-applicable rules + content of any name-matched rule, with the note from the `## Repo Rules` section of the review discipline (included below).

Spawn all agents simultaneously in a single parallel batch — all pass-1 agents and all pass-2
agents at once. Pass 2 does not wait for pass 1. Collect findings from all agents (both passes)
before proceeding to Phase 3.

Spawn each agent with `model: sonnet`. The merged reviewer list (from the pre-loaded context above)
includes all agents — built-ins, repo overrides (same name as a built-in, repo version wins), and
repo-specific agents (new names not in the built-in set). Run all of them. For each agent, the
file path is `.claude/agents/reviewers/<name>.md` if it exists there, otherwise
`${CLAUDE_SKILL_DIR}/agents/<name>.md`. context.sh resolves this — you just work from the list.

Use this prompt for **both passes** — the only difference is the diff passed at the end (normal for pass 1, reversed for pass 2):

> "Read `<agent-file>` for your reviewer persona and focus areas. Read `CLAUDE.md` for project conventions. Review the following diff from your specialized perspective. If a work plan is provided below, use it to understand the *intent* of the change — but evaluate the code on its own merits. Intentional changes can still be wrong. Output all findings using the standard finding format provided below.
>
> If you find no issues in your domain, say so explicitly — do not manufacture findings to justify your involvement. A clean review is a good outcome.
>
> READ ONLY — no edits, no tests, no commits.
>
> You have a budget of 10 tool uses. The diff is provided below — do not browse the codebase beyond what is needed to understand a specific finding. Report all findings identified so far if you approach the limit.
>
> [finding format content]
>
> [review discipline content]
>
> [applicable repo rules, if any]
>
> [diff for this pass]"

---

## Phase 3: Synthesis

After all reviewers complete:

1. Collect all findings — actionable findings MUST use the standard finding format. Informational `[NOTE]` outputs go into the `## Informational Notes` section as unchecked `[ ]` items (see step 9).

2. **Coordinator sweep (gap-finding).** Before deduplication, review the full set of specialist findings alongside the diff. As coordinator you have unique vantage: you see everything all specialists found and everything they collectively did not address. Look for cross-cutting issues that fall between domains — a correctness problem that also breaks testability, a security fix that silently changes an API contract, code that works in isolation but behaves differently under concurrent load. Add any such findings as new entries with `**Reviewer:** coordinator`. Do not repeat findings the specialists already caught.

3. Deduplicate — merge findings that flag the same issue. When merging, set `**Reviewer:**` to a comma-separated list of all agents that flagged it (e.g., `react, typescript`). When multiple reviewers independently flagged the same issue, note this agreement in the **Description** or synthesis narrative as a signal of higher confidence. **Multi-pass agreement:** if the colliding findings came from different passes of the same agent (e.g., `security` pass 1 and `security` pass 2), that is a meaningful confidence signal — keep the higher-confidence variant, set `**Reviewer:**` to `<name> (confirmed across passes)`, and note the agreement in the **Description**. If pass 2 contributed zero findings that survived deduplication, note that in the synthesis narrative (indicates pass 1 was thorough or the diff has little position-dependent variation).

4. **Cross-reference against existing PR feedback.** If the Existing Feedback Digest (built in Phase 1) is non-empty, compare each surviving finding against it. If the digest is empty or was not fetched (no PR), skip this step.

   **Matching criteria** (use your judgment — you are an LLM, not a string matcher):
   - **Location match (strongest):** the finding's `**File:**` references the same file AND an overlapping or nearby line range (within ~10 lines) as an inline review comment
   - **Semantic match:** even without exact line overlap, the finding and the existing comment describe the same logical concern (e.g., both flag the same missing null check, same error handling gap, same refactoring opportunity)
   - For review summaries and issue comments (no line anchor): match by semantic similarity only
   - **Not a match:** same concern but in a completely different file — that is a separate occurrence

   **Disposition rules** — for each match, apply based on the thread's resolution signal:

   | Resolution signal | Disposition |
   |---|---|
   | `intentional` — author explained why it's deliberate | **Drop.** The author already defended this to a human reviewer. Re-raising it signals the tool isn't paying attention. |
   | `acknowledged` — author agreed, will fix | **Keep but annotate.** Append to Description: "Also flagged by @{reviewer} (author acknowledged, fix pending)." No confidence change. Drop only if the current diff already includes the fix. |
   | `already-fixed` — author claims it's fixed | **Drop**, but verify the issue is actually gone in the current code. If still present, keep with note: "Author claimed fixed but issue appears to persist." |
   | `disputed` — author pushed back, unresolved | **Keep but annotate.** Append to Description: "Note: @{reviewer} raised a similar concern; the author pushed back — see the PR thread for context." Demote confidence by 15 points. |
   | `no-response` — no author reply | **Keep but annotate.** Append to Description: "Also flagged by @{reviewer} (no author response yet)." No confidence change — independent agreement adds weight. |

   Record all dispositions (drops, demotions, annotations) for the `## Human Feedback Cross-Reference` section of the review document.

   **Reverse direction — incorporate unmatched human feedback.** After the dedup pass above, check for digest entries that were NOT matched by any surviving finding. These are human concerns the automated review missed. For each unmatched entry: evaluate the concern against the current code. If valid and unresolved, create a new finding with `**Reviewer:** coordinator (from @{commenter} PR feedback)` and apply standard severity/confidence assessment. If already resolved in the current diff, note it as resolved in the cross-reference section. Record all outcomes (surfaced as finding, or resolved) in the `## Human Feedback Cross-Reference` section alongside the matched dispositions.

5. **Confidence-based pre-check.** Apply the confidence score to set the initial checkbox state — do not discard findings:
   - **>= 70**: pre-checked `[x]` — agent is confident; reviewer opts out if they disagree
   - **50–69**: pre-unchecked `[ ]` — agent flagging it but not confident; reviewer opts in if they agree
   - **< 50**: move to `## Informational Notes` — speculative; worth knowing but not claiming action is needed

6. **Filter against intent** — for each finding, check it against the PR plan and diff context. Ask: "is the behavior being flagged consistent with the stated intent of this change?" If yes, demote to `[NOTE]` or drop it entirely. Log your reasoning briefly (e.g., "dropped: reviewer flagged missing X, but X is intentionally omitted per the plan"). Reviewers see individual files; the coordinator sees the whole picture — use that advantage.

   **Pre-existing issues in touched files are still valid findings.** Do not dismiss a finding simply because the problem existed before this PR. If the file was directly modified by this PR, the author had the opportunity to notice and fix it — flagging it is appropriate. Only dismiss pre-existing issues in files the PR did not touch at all.
7. Sort by severity: BLOCKER > ISSUE > SUGGESTION > NIT.
8. Within each severity level, group by file or theme.
9. Flag conflicts — if reviewers disagree, note both views and mark for user decision.
10. Collect `[NOTE]` outputs into the `## Informational Notes` section as **unchecked** `[ ]` items — no ref IDs. Unchecked means the coordinator doesn't recommend action, but the user can check one and say "fix this too" to include it in Phase 4.

### Save the review document

- Filename: `<slug>.review.<YYYY-MM-DD>-<short-sha>.md` (slug from branch name, short-sha = HEAD 7 chars)
- Save to `.work/<ticket>/reviews/` (create the `reviews/` directory if needed)
- If no ticket directory found, save to `.work/general/reviews/`

```markdown
---
skill: code-review
phase: review-complete
sha: <head-commit-sha>
instruction: |
  This is a code-review report. High-confidence findings are pre-checked [x] (opt-out model).
  Lower-confidence findings are pre-unchecked [ ] (opt-in model) — the reviewer decides whether
  to act on them.
  If the user says "go", "fix", or similar — FIRST READ the code-review skill
  (find it at `~/.claude/skills/code-review/SKILL.md`), then execute
  Phase 4 (Fix) for all [x] checked findings. Skip any unchecked [ ] ones.
  User **Instructions** on each finding take priority over reviewer suggestions.
---

# Code Review: [branch-name]

> [One-line summary of what this change does]
> Reviewed: [date] | Reviewers: [list] | Scope: [incremental from <sha> | full PR]

## Summary

- X blockers, Y issues, Z suggestions, W nits
- [Brief narrative: overall quality, notable strengths, key concerns]

## Human Feedback Cross-Reference

> N findings matched existing PR feedback and were suppressed.

| Finding | Matched | Disposition |
|---------|---------|-------------|
| [brief description of suppressed finding] | @reviewer [inline/review], resolution signal | Dropped — [reason] |
| [brief description of annotated finding] | @reviewer [inline], no-response | Kept — annotated |

[Omit this section entirely if no existing PR feedback was found]

## Findings

### Blockers
[findings in standard format, ref IDs F1, F2, ... — `[x]` if confidence >=70, `[ ]` if 50–69]

### Issues
[findings — `[x]` if confidence >=70, `[ ]` if 50–69]

### Suggestions
[findings — `[x]` if confidence >=70, `[ ]` if 50–69]

### Nits
[findings — `[x]` if confidence >=70, `[ ]` if 50–69]

## Informational Notes

[unchecked `[ ] **[NOTE]** ...` items — omit this section if empty]

## Review Notes

[Space for user to add overall notes or context]
```

Present the review to the user. Walk through highlights. Ask them to:
- Uncheck `[ ]` any findings to skip
- Add specific guidance in the `**Instructions:**` field on any finding
- Say "go" when ready for fixes

**STOP. Do not begin Phase 4 until the user says "go" (or equivalent: "fix", "proceed", "lgtm").
Pre-checked findings are reviewer defaults — they are not the user's approval to start fixing.
Discussing the review, asking follow-up questions, or saying "looks good" is not a go-ahead.
Wait for an explicit instruction.**

*Exception — full auto mode only:* if the session was started with "full auto", proceed to
Phase 4 immediately after presenting the review without waiting.

---

## Phase 4: Fix

> **Gate check:** Phase 4 requires the user's explicit "go" (or equivalent). If you haven't received it, return to Phase 3 and wait.

Update the review doc's `phase:` to `fixes-in-progress`.

### Step 1: Group findings into fix batches

Findings touching the same file(s) MUST be in the same batch (prevents edit conflicts). Non-overlapping batches can run as parallel agents. Each batch: 1–5 findings.

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

**Maximize parallelism.** Look at the batches from Step 1. All batches that touch non-overlapping files can (and should) be spawned as parallel agents simultaneously — a single message with multiple Agent tool calls, not sequential spawns. Only serialize batches that share files. For a typical review with 3–7 findings across different files, most or all batches should run in parallel.

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

Update the review doc as agents report back:
- `[x]` → `[fixed]` after editing, with one-line change summary
- `[fixed]` → `[verified]` after verification passes (batch-update)
- If verification fails, leave as `[fixed]` and append what failed
- `[ ]` → `[skipped]` for unchecked findings

### Step 5: Verify (centrally, after ALL edits complete)

**Do not run verification until all edit agents have reported back.**

1. **Read CLAUDE.md** to find the repo's verification commands.
2. **Format** changed files only (runs first — it modifies files):
   - Get changed files: `git diff $(git merge-base HEAD main)...HEAD --name-only`
   - Use repo-appropriate formatter from CLAUDE.md
3. **Typecheck + Tests** in parallel:
   - Use the typecheck command from CLAUDE.md
   - Tests: only test files related to changes (use filename patterns as filters, not full suite)

If verification fails, fix issues (spawn new agents if needed), then re-verify.

### Step 6: Resolve All Findings

Before committing, scan the review document and ensure every checked `[x]` finding has been updated to a terminal status. No finding should still show bare `[x]` at this point.

Terminal statuses: `[fixed]` → `[verified]`, `[skipped]`, `[will-not-do]`, `[deferred]`, `[already-resolved]`, `[could-not-prove]`.

If any checked findings are still `[x]`: update them now — mark `[skipped]` with a note if they were intentionally not addressed, or `[deferred]` if out of scope.

**Auto-proceed (post-fix only):** Once fixes are complete and verification passes, immediately
continue to Steps 7, 8, and 9 — commit, push, then post the PR comment — without stopping to
ask. The user's "go" at Phase 4 entry authorizes the full fix cycle through commit and push.
Only pause mid-cycle if: (a) verification still fails after fix attempts, (b) a finding requires
a judgment call not covered by the user's instructions, or (c) an unanswered question came up
that needs a decision before proceeding. This auto-proceed applies *after edits are complete* —
not at Phase 4 entry, which always requires the user's explicit "go".

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

> "Read `${CLAUDE_SKILL_DIR}/references/code-review-summary-format.md` for the exact comment format — follow it precisely, do not invent a different layout.
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
> 2. If found → update that comment with `gh api repos/<owner>/<repo>/issues/comments/<id> -X PATCH --field body="<formatted>"` (this is a resumed partial post)
> 3. If not found → post a new comment with `gh pr comment <pr-number> --body "<formatted>"`
>
> Extract the comment ID from the gh output (the numeric ID at the end of the comment URL, e.g. `4155206998` from `...#issuecomment-4155206998`) and return it."

If no PR exists, skip this step — the review doc stays local.

---

## Phase 5: Retrospective

After the session:
1. **Ensure the PR comment is current.** Check whether a PR summary comment has been posted covering all review cycles in this session. This applies regardless of how fixes were made — formal Phase 4, ad-hoc fixes through discussion, or a mix. For each review doc in `.work/<ticket>/reviews/` that was active this session: if no comment was posted (including cases where the session ended between Step 8 push and Step 9 comment), post one now using the Step 9 sub-agent. If a comment was posted but findings changed after it (e.g., additional fixes were pushed), post an updated comment.
2. Summarize what was found, fixed, and deferred.
3. Ask the user if any review agents or this skill should be updated based on what was missed or noisy.
4. With user approval, suggest edits to the relevant `.claude/agents/reviewers/` files.

**Next step:** If the PR has reviewer feedback to address, run `/handle-pr-feedback`. Otherwise, merge the PR.

---

## Agent Budgets

Agents can get stuck. Include budget instructions in every agent prompt.

| Agent type             | Budget         | On budget hit                                    |
|------------------------|----------------|--------------------------------------------------|
| Reviewer agent         | 10 tool uses   | Report findings identified so far and stop       |
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
- **Files to skip in review:** `**/generated/**`, `*.generated.*`, `schema.json`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `*.pyc`, `*.lock`
- **Session continuity:** Before ending, ensure the review document is saved with current `phase:` and findings state.
- **PR comment is an invariant, not a step.** After any push during a review session, a PR comment for this review round must exist and reflect the current outcome. Each review round gets its own comment (keyed by `<!-- code-review: <review-sha> -->` marker, where `<review-sha>` is the 7-char SHA from the review doc filename — see Step 9 and the summary format reference). Phase 4 Step 9 handles this in the formal fix flow. Phase 5 is the catch-all — if fixes happened through discussion, ad-hoc edits, or any path that bypassed Phase 4, Phase 5 will catch it. The comment must exist and be current before the session ends.
