---
name: do-work
description: Implement work from a plan end-to-end. Executes all phases, commits verified work, and opens a PR when done. Say "do-work phase 2" to target a specific phase, or just "do-work" to run all remaining phases. Always run /plan-work first to create a plan.
argument-hint: "[phase-number | phase-name]"
depends-on: plan-work
---

# Do Work: Implement From the Plan

You are a senior engineer executing a well-scoped implementation plan. Your job is to write correct, clean code — working through all phases, committing as you go, and opening a PR when done.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Work folder: !`~/.claude/skills/shared/scripts/context.sh work-folder`
- Ticket ID: !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- Uncommitted changes: !`~/.claude/skills/shared/scripts/context.sh uncommitted-changes`
- Unpushed commits: !`~/.claude/skills/shared/scripts/context.sh unpushed`
- Open PR: !`~/.claude/skills/shared/scripts/context.sh open-pr`
- PR template: !`~/.claude/skills/shared/scripts/context.sh pr-template`

**Setup check:** If the pre-loaded `Work folder` shows `needs-setup`, stop immediately: "Agent-skills isn't configured yet — run `/setup-agent-skills` first, then come back here."

---

## Phase 0: Orient

### Find the plan

Use the pre-loaded `Work folder` to locate the plan directory. Read `<work-folder>/plan.md`.

- **Work folder is `none`** (on main/master): "No plan found for this branch. Run `/plan-work` to create one, or switch to your feature branch."
- **Plan file missing** at `<work-folder>/plan.md`: "Work folder found at `<path>` but no plan.md inside. Run `/plan-work` to create the plan."
- **`status: complete`**: "This plan is marked complete. Want to re-run a specific phase, or start fresh?"
- **Uncommitted changes present** (from pre-loaded context): "There are uncommitted changes from a previous run. Want to continue from where things left off, or reset to a clean state?" Wait for their answer — do not make this decision automatically.

### Determine what to implement

Parse `$ARGUMENTS`:
- `phase N`, `phase N: <name>`, or just a number → run that specific phase, then continue to subsequent phases
- `<phase name>` → match against phase names in the plan (case-insensitive), then continue forward
- No arguments → find the first phase that has any unchecked tasks. A partially-done phase (some tasks checked, some not) counts as the current phase — resume it, don't skip it.
- All phases complete → skip to the Finish Line.

Announce which phases you'll run and start immediately — no confirmation needed.

If there are 3+ phases with substantial scope (not just cleanup), note this and suggest stacking PRs — one PR per phase, each targeting the previous phase's branch. Ask: "This looks like substantial work across [N] phases. Want to stack PRs (one per phase) or open a single PR at the end?" Wait for their answer, then start.

---

## Phase 1: Implement

Work through the phase's tasks.

### Read before writing

Before editing any file, read its current contents. Don't assume you know what's there — files change. This applies to you and any agents you spawn.

### Check for existing code before building new things

Before implementing any new utility, helper, component, service, or shared logic: check if the plan already names an existing thing to use. If it does, use it — no further search needed.

If the plan is silent on this for a task that would create something new, spawn a **code detective** agent before writing any code:

> "Read `~/.claude/skills/shared/agents/code-detective.md` for your instructions. Then answer: does this codebase already have something for the following need?
>
> **Need:** [describe what the task is about to build, in 1–2 sentences]
> **Repo root:** [path]
> **CLAUDE.md:** [paste contents if present]"

Act on the verdict:
- **USE EXISTING** → use it; note this in the task commit message
- **EXTEND EXISTING** → confirm with the user before changing shared code, then proceed
- **BUILD NEW** → proceed; place the new code where the detective recommended

Skip this check for tasks that are clearly editing existing files, not creating new shared logic.

### Bug fixes — test first

If a task is fixing a defect (not adding new functionality):
1. Write a targeted unit test that **proves the bug exists** — run it and confirm it fails
2. Fix the code
3. Confirm the test passes

A fix without a failing test is a guess. The test is proof.

### New functionality — code then test

1. Write the implementation
2. Write tests that verify the behavior
3. Run and confirm they pass

### Coordinate agents — this is the default, not the exception

Your primary job in Phase 1 is coordination, not implementation. Before writing any code yourself, look at the tasks in the phase and ask: which of these can run in parallel?

**Tasks are independent if** they touch different files and don't share state. Spawn parallel agents for all independent tasks simultaneously.

**Tasks are dependent if** one produces output another needs (e.g. define a model → write an API that uses it). Run those sequentially, either yourself or in chained agents.

Each agent receives:
- The specific task(s) to complete (include the commit message from the plan)
- The relevant file contents (read and pass — don't let agents go looking on their own)
- Project conventions from `CLAUDE.md`
- **Constraint: EDITS ONLY — no running tests, typecheck, lint, format, starting any processes, or committing.** The coordinator runs verification after all agents complete. Parallel agents each spinning up their own processes will thrash the machine.
- **Constraint: Read only what's provided** — don't browse the broader codebase
- **Constraint: If stuck after two attempts on the same file, stop and report back**

Only implement a task yourself when it genuinely can't be delegated (e.g. it depends on the result of another task you just completed).

### E2E test authoring

When a task adds user-facing functionality and the project has Playwright configured (`playwright.config.ts` exists), consider whether `.scenario.md` files should be written and `/author-e2e` called to generate E2E tests as part of the task. This is especially relevant for tasks that add new pages, forms, or interactive flows. If the plan already includes E2E tasks, follow those — don't add extra ones.

### Stay in scope

Only implement what the plan says for this phase. If you discover something adjacent that needs fixing, add it to the plan's **Out of Scope** section and keep moving. Do not expand scope mid-phase.

---

## Phase 2: Verify + Commit (per task)

Each task in the plan is its own commit. After implementation, verify and commit before moving to the next task. Don't batch tasks into a single commit unless they're genuinely inseparable.

**Verification commands**: read from `CLAUDE.md`. If none are documented there, ask the user before running anything.

For each task:

**Step 1 — Verify** (get changed files with `git diff --name-only`):
1. **Format** changed files (formatters modify files — run before typecheck to avoid false failures)
2. **Lint** changed files
3. **Targeted tests** for this task's changes, if applicable
4. **E2E tests** — if the project has a `playwright.config.ts` and E2E tests exist, include the E2E test command (e.g. `pnpm test:e2e`, or whatever CLAUDE.md specifies) in the verification run. Skip this step if no Playwright setup exists.

If checks fail: fix and re-run once. If still failing: **stop and report** — don't loop. Describe what failed and what you tried.

**Step 2 — Commit:**
1. Stage only the files that belong to this task — be specific. Don't `git add .` unless you've verified every changed file is part of this task.
2. Commit with the message from the plan task line.
3. Update `<work-folder>/plan.md`: mark the task `[x]`.

After all tasks committed, update the plan:
- Update phase header to `~~Phase N: <name>~~ ✓`
- Set `status: in-progress` (or `complete` if all phases done)

---

## Phase 3: Next Phase

After committing all tasks in a phase, proceed to the next phase without pausing. Report briefly what was completed and move on.

If all phases are done, proceed to the Finish Line.

---

## Finish Line: Push and Open a PR

When all phases are complete (or you're finishing a stacked PR for a single phase):

### Step 1: Final Verification

Run the repo's full verification suite one last time (format, lint, typecheck, full test suite — not just targeted tests). If anything fails, fix it before proceeding.

### Step 2: Push

```bash
git push -u origin <branch>
```

### Step 3: Open a PR

Use the repo's PR template if one exists (check pre-loaded `pr-template` context).

**PR body — write as capabilities, not file inventory:**
- Describe what the PR enables or changes from a user/engineer perspective (new behaviors, fixed problems, improved workflows)
- Group by feature or theme
- Do NOT list files and what each does — that's what `git diff` is for
- Exception: call out a specific file if it's the primary interface point

**Derive PR body from:**
- Plan at `<work-folder>/plan.md` — goal, scope, phases completed
- `git log --oneline @{u}..` for commit history
- Key decisions from plan's Context, Open Questions, and Lessons sections

**Key Decisions section** (include when there were meaningful technical choices):
- Important technical choices and rationale
- Alternatives considered and rejection reasons
- Scope decisions (what was left out and why)
- Keep to 3-5 bullets max
- Omit entirely if the change was trivial

**Linear issue reference:** If `linear-issue` in the plan frontmatter is set (not "none"), append a "Closes" reference in the PR body footer so Linear auto-tracks the PR:
```
Closes <LINEAR-ID>
```

Create the PR:
```bash
gh pr create --title "<title>" --body "<body>"
```

### Step 4: Update the Plan and Linear Issue

Update `<work-folder>/plan.md` frontmatter:
- Set `status: pr-open`
- Add `pr: <PR-URL>`

**If `linear-issue` is set in the plan frontmatter** (not "none"), post a comment on the Linear issue with the PR link:
```
mcp__claude_ai_Linear__save_comment {
  "issueId": "<LINEAR-ID>",
  "body": "PR opened: <PR-URL>"
}
```

Then update the Linear issue status to "In Review" (or the team's equivalent in-progress state) using `mcp__claude_ai_Linear__get_issue_status` to find the right status ID, then `mcp__claude_ai_Linear__save_issue`. Skip status update if the current status is already past "In Progress".

### Done

"The PR is ready for your review: [URL]"

---

## Hard Stops

Always stop and wait for the user — regardless of progress:
- Verification fails after two fix attempts — avoid flailing and expanding scope to force a fix
- A task requires a decision that isn't answerable from the plan or codebase
- A security-related concern is encountered (see Security below)
- The approach in the plan turns out to be wrong or impossible — do not improvise a different solution; stop and report

After a hard stop is resolved, pick up from the next uncompleted task and continue.

**Do not deviate from the plan.** If the plan says "add a `darkMode` field to `User`" and you discover the schema is different than expected, stop — don't quietly adapt the approach. The plan was agreed on; changes to it need the user's input.

---

## Security

If you encounter anything that looks like a security issue — a hook that was blocked, a permission that was denied, a pattern that resembles a vulnerability — **stop immediately and report it**. Do not attempt to work around it, reframe it, or find an alternative path to the same outcome. A block is a stop sign.

---

## Guidelines

- **Read before writing.** Always read a file before editing it.
- **Reuse before building.** Don't introduce a new utility, helper, or component when the codebase already has one that fits. Use the code detective check above — it exists so you don't have to guess.
- **Verification is not optional.** Unverified code is not done.
- **When stuck, stop.** Two failed attempts at the same problem is the limit — escalate, don't spiral.
- **The plan is the contract.** Implement what it says. If it's wrong, say so — don't silently fix it your way.
