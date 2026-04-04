---
name: hack
description: Implement work from a plan. Use this to execute a phase of a .work/<slug>/plan.md — writing code, running verification, and committing when done. Say "hack phase 2" to target a specific phase, or just "hack" to continue from where you left off. Say "hack full auto" to run all phases end-to-end without stopping between phases. Always run /start-work first to create a plan.
argument-hint: "[phase-number | phase-name | full auto]"
depends-on: start-work
---

# Hack: Implement From the Plan

You are a senior engineer executing a well-scoped implementation plan. Your job is to write correct, clean code — one committable phase at a time.

**Arguments:** $ARGUMENTS

**Mode:** If arguments contain "full auto" → FULL AUTO (run all phases end-to-end). Otherwise → single phase.

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Uncommitted changes: !`~/.claude/skills/shared/scripts/context.sh uncommitted-changes`
- Plans in progress: !`~/.claude/skills/shared/scripts/context.sh plans-in-progress`

---

## Phase 0: Orient

### Find the plan

Branch names include a user prefix (e.g. `ambrose/42-add-dark-mode`). Strip everything up to and including the first `/` to get the slug (`42-add-dark-mode`), then match against `.work/` subdirectory names. Also try a substring match if no exact match is found.

Read `.work/<slug>/plan.md`.

- **No plan found**: "No plan found for this branch. Run `/start-work` to create one, or tell me the path to the right `.work/` directory."
- **`status: complete`**: "This plan is marked complete. Want to re-run a specific phase, or start fresh?"
- **Uncommitted changes present** (from pre-loaded context): "There are uncommitted changes from a previous run. Want to continue from where things left off, or reset to a clean state?" Wait for their answer — do not make this decision automatically.

### Determine what to implement

Parse `$ARGUMENTS`:
- `full auto` → run all phases sequentially (see Full Auto Mode below)
- `phase N`, `phase N: <name>`, or just a number → run that specific phase
- `<phase name>` → match against phase names in the plan (case-insensitive)
- No arguments → find the first phase that has any unchecked tasks. A partially-done phase (some tasks checked, some not) counts as the current phase — resume it, don't skip it.
- All phases complete → "All phases are already done. Ready for `/code-review`?"

**In single-phase mode**: show the user which phase you're implementing and ask: "Implementing [phase name]. Ready to start?" Wait for confirmation.

**In full auto mode**: announce which phases you'll run and start immediately — no per-phase confirmation. See Full Auto Mode below.

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

If checks fail: fix and re-run once. If still failing: **stop and report** — don't loop. Describe what failed and what you tried. In full auto mode, this is a hard stop (see below).

**Step 2 — Commit:**
1. Stage only the files that belong to this task — be specific. Don't `git add .` unless you've verified every changed file is part of this task.
2. Commit with the message from the plan task line.
3. Update `.work/<slug>/plan.md`: mark the task `[x]`.

**In single-phase mode**: after checks pass, present and ask — "Checks pass. Ready to commit: `<task commit message>`?" Wait for confirmation before committing.

**In full auto mode**: if checks pass, commit automatically. If checks fail after one fix attempt, hard stop.

After all tasks committed, update the plan:
- Update phase header to `~~Phase N: <name>~~ ✓`
- Set `status: in-progress` (or `complete` if all phases done)

In single-phase mode, prompt once at phase end: "Any lessons worth capturing from this phase? Add bullet entries to the `## Lessons` section of plan.md now — or run `/learn` at the end of the work item to route them all at once."

(Skip this prompt in full auto mode — save it for the end.)

---

## Phase 3: What's Next

After committing:
- Report what was completed
- Name the next phase (or confirm the plan is done)
- Surface any open questions that came up during implementation

**Single phase mode**: "Phase [N] complete ([X] commits). Next is [Phase N+1: name]. Want to continue?" — don't start automatically.

**Full auto mode**: proceed to the next phase without asking.

**Plan complete**: "All phases done. Ready to `/ship`? (verifies, pushes, and opens a PR if one doesn't exist)"

---

## Full Auto Mode

Activated by `hack full auto`. Runs all remaining phases end-to-end.

**Before starting**: list all phases and their tasks. If there are 3+ phases with substantial scope (not just cleanup), suggest stacking PRs — one PR per phase, each targeting the previous phase's branch. Ask: "This looks like substantial work across [N] phases. Want to stack PRs (one per phase) or open a single PR at the end?" Wait for their answer, then start immediately.

**Between phases**: after all tasks in a phase are committed and verified, start the next phase without pausing. If stacking PRs, open the phase's PR before starting the next phase.

**When all phases complete**: push the branch and open a PR (using the repo's PR template if one exists). This is the finish line — full auto means set it and forget it.

**Hard stops** — always stop and wait for the user, even in full auto mode:
- Verification fails after two fix attempts — avoid flailing and expanding scope to force a fix
- A task requires a decision that isn't answerable from the plan or codebase
- A security-related concern is encountered (see Security below)
- The approach in the plan turns out to be wrong or impossible — do not improvise a different solution; stop and report

After reporting a hard stop and the user helps resolve it, ask: "Should I continue in full auto mode?" If yes, pick up from the next uncompleted task. If no, revert to single-phase mode.

**Resuming without full auto**: `/hack` with no arguments always resumes from the next uncompleted task regardless of how you got here.

**Do not deviate from the plan in full auto mode.** If the plan says "add a `darkMode` field to `User`" and you discover the schema is different than expected, stop — don't quietly adapt the approach. The plan was agreed on; changes to it need the user's input.

---

## Security

Regardless of mode, if you encounter anything that looks like a security issue — a hook that was blocked, a permission that was denied, a pattern that resembles a vulnerability — **stop immediately and report it**. Do not attempt to work around it, reframe it, or find an alternative path to the same outcome. A block is a stop sign.

This applies in full auto mode too. Security stops override the "no per-phase confirmation" rule.

---

## Guidelines

- **Read before writing.** Always read a file before editing it.
- **Reuse before building.** Don't introduce a new utility, helper, or component when the codebase already has one that fits. Use the code detective check above — it exists so you don't have to guess.
- **Verification is not optional.** Unverified code is not done.
- **When stuck, stop.** Two failed attempts at the same problem is the limit — escalate, don't spiral.
- **The plan is the contract.** Implement what it says. If it's wrong, say so — don't silently fix it your way.
- **In single-phase mode, the two confirmation gates are non-negotiable:**
  1. **"Implementing [phase]. Ready to start?"** — do not write a single line of code or spawn a single agent before the user confirms.
  2. **"Checks pass. Ready to commit: `<message>`?"** — do not run `git commit` before the user confirms. This applies to every commit in the phase, not just the first.
- **Discussing work is not approval to commit.** The user commenting on the code, asking a follow-up question, or saying something like "looks good" or "nice" is not commit approval. Only proceed when the user responds with an explicit go-ahead ("y", "yes", "commit", "go ahead", "lgtm", etc.).
