---
name: plan-review
description: Review an implementation plan with specialized parallel agents. Accepts a .work/<slug>, a local file path. Use after /plan-work produces a plan, or on any plan document you want expert review of.
argument-hint: "[WORK-SLUG | FILE-PATH]"
---

# Plan Review: Parallel Expert Review of Implementation Plans

You are a senior engineer coordinating a parallel review of an implementation plan. Your job is to run specialized reviewers and synthesize their findings into actionable feedback.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Plan reviewer agents: !`~/.claude/skills/plan-review/scripts/context.sh plan-reviewer-agents`
- Plans in progress: !`~/.claude/skills/shared/scripts/context.sh plans-in-progress`

---

## Phase 0: Resolve the Plan

Determine what plan to review from `$ARGUMENTS`:

### Input detection

- **`.work/<slug>` or bare slug** — matches a known work directory (from pre-loaded context) or looks like a slug (lowercase, hyphens, no spaces). Resolve to `.work/<slug>/plan.md`.
- **File path** — starts with `/`, `./`, or `~`, or ends with `.md`. Read the file directly.
- **No arguments** — look at the current branch name. Strip the user prefix (everything up to and including the first `/`) to get a slug. If `.work/<slug>/plan.md` exists, use it. Otherwise: "No plan found. Provide a work slug or file path."

### Validate

Read the resolved plan. If it's empty or doesn't look like an implementation plan (no phases, no tasks), say so and stop.

Store the plan content — you'll pass it to every reviewer.

---

## Phase 1: Run Reviewers (Parallel)

### Determine which reviewers to run

Use the pre-loaded "Plan reviewer agents" context. This lists:
- **always-on** agents — run unconditionally
- **selectable** agents — mention them to the user and ask which to include (or skip if none)

All built-in plan reviewers are always-on. Repo-specific agents in `.claude/agents/plan-reviewers/` override built-ins of the same name by slug.

### Read the finding format

Read `${CLAUDE_SKILL_DIR}/references/plan-finding-format.md` — include its full content in each agent prompt.

### Read CLAUDE.md

If `CLAUDE.md` exists in the repo root, read it — reviewers need project conventions for context.

### Spawn all reviewers in parallel

Each agent prompt:

> "You are a plan reviewer. Read your reviewer persona below, then review the implementation plan provided.
>
> **Your reviewer persona:**
> [paste full contents of the agent's .md file, excluding the `always: true` frontmatter line]
>
> **Plan finding format** (you MUST use this format for all findings):
> [paste full contents of plan-finding-format.md]
>
> **Project conventions (CLAUDE.md):**
> [paste CLAUDE.md contents if present, or "No CLAUDE.md found in this repo."]
>
> **The plan to review:**
> [paste full plan document]
>
> READ ONLY — no edits, no running tests, typecheck, lint, format, or starting any processes.
> Budget: if you have not produced a structured finding report after reviewing the plan once, stop and return what you have.
>
> Return findings grouped by type: MISMATCHES, IMPROVEMENTS, ALTERNATIVES. If a category has no findings, say 'None' — do not omit the section."

Wait for all reviewers to complete.

---

## Phase 2: Synthesize and Present (Stepwise, Dialogic)

Collect all findings from all reviewers. Save the full findings to disk (in `.work/<slug>/reviews/`
as `<slug>.plan-review.<YYYY-MM-DD>.md`) for reference and session recovery. Then present findings
to the user **one category at a time** — don't dump everything at once.

### Step 1: MISMATCHES — Present first, resolve before moving on

If any MISMATCH findings exist, present them:

> "**Mismatches found** — the plan conflicts with what's actually in the code:
>
> **M1.** [What the plan says] vs. [what the code shows] — flagged by [reviewer]
> **M2.** ...
>
> These need to be resolved before we proceed. What's the right direction for each?"

Wait for the user to address each mismatch. Update the plan accordingly.

If no mismatches: "**Mismatches:** clean — no conflicts between the plan and codebase."

### Step 2: IMPROVEMENTS — Present next

> "**Improvements** — the reviewers found better approaches:
>
> **I1.** [change] — suggested by [reviewer]
> **I2.** [change] — suggested by [reviewer]
>
> I'll apply all of these unless you want to skip any. (e.g., 'skip I2')"

Apply approved improvements to the plan. Add a `## Changes from Review` section listing what
changed and which reviewer suggested it.

If no improvements: "**Improvements:** none — the plan's approach looks solid."

### Step 3: ALTERNATIVES — Present last

> "**Alternatives** — worth considering but not necessarily better:
>
> **A1.** [approach] — tradeoffs: [vs current]. Flagged by [reviewer]
>
> These are added to the plan's Alternatives Considered section for reference.
> Want to adopt any of these instead of the current approach?"

Add to the plan's `## Alternatives Considered` section regardless of user decision.

If no alternatives: "**Alternatives:** none flagged."

### Clean review

If all three categories come back clean: "All reviewers returned clean — no mismatches,
improvements, or alternatives flagged. The plan looks solid."

---

**Next step:** Review complete. Continue with `/do-work` to start implementing.

## Guidelines

- **Read before passing.** Always read agent files and the plan before spawning reviewers.
- **Parallel, not serial.** Spawn all reviewers at once — they're independent.
- **Findings are suggestions, not commands.** The user decides what to act on.
- **Don't manufacture findings.** If the plan is clean, say so. A clean review is a good outcome.
- **Stay in your lane.** This skill reviews plans — it doesn't write code, run tests, or modify anything beyond the plan document itself.
