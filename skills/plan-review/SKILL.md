---
name: plan-review
description: Review an implementation plan with specialized parallel agents. Accepts a work slug, a full path, or no argument (auto-discovers from current branch). Use after /plan-work produces a plan, or on any plan document you want expert review of.
argument-hint: "[WORK-SLUG | FILE-PATH]"
---

# Plan Review: Parallel Expert Review of Implementation Plans

You are a senior engineer coordinating a parallel review of an implementation plan. Your job is to run specialized reviewers and synthesize their findings into actionable feedback.

**Arguments:** Use the arguments supplied with this skill invocation or the user's current request.

Read `~/.agent-skills/skills/shared/references/harness-capabilities.md` before proceeding. Use its active-harness mappings for skills, questions, progress, delegation, model tiers, project instructions, and connected tools.

**Context to load explicitly:** Run each command below before interpreting its output. These are shell commands to execute, not values supplied automatically by the harness.

- Work folder: `bash ~/.agent-skills/scripts/shared/context.sh work-folder`
- Ticket ID: `bash ~/.agent-skills/scripts/shared/context.sh ticket-id`
- Plan reviewer agents: `bash ~/.agent-skills/scripts/plan-review/context.sh plan-reviewer-agents`

**Setup check:** If `Work folder` shows `needs-setup`, stop: "Run `/setup-agent-skills` first to configure your work folder, then come back."

---

## Phase 0: Resolve the Plan

Determine what plan to review from the invocation input:

### Input detection

- **Bare slug** — looks like a slug (lowercase, hyphens, no spaces). Resolve to `<work-folder>/plan.md` using the configured work root.
- **File path** — starts with `/`, `./`, or `~`, or ends with `.md`. Read the file directly.
- **No arguments** — use the loaded `Work folder`. If not "none", resolve to `<work-folder>/plan.md`. If "none": "No plan found. Provide a work slug or file path, or switch to your feature branch first."

### Validate

Read the resolved plan. If it's empty or doesn't look like an implementation plan (no phases, no tasks), say so and stop.

Store the plan content — you'll pass it to every reviewer.

---

## Phase 1: Run Reviewers (Parallel)

### Determine which reviewers to run

Use the loaded "Plan reviewer agents" context. This lists:
- **always-on** agents — run unconditionally
- **selectable** agents — mention them to the user and ask which to include (or skip if none)

All built-in plan reviewers are always-on. For each exact slug, use `.agents/plan-reviewers/<name>.md` first, then legacy `.claude/agents/plan-reviewers/<name>.md`, then the built-in persona at `~/.agent-skills/skills/plan-review/agents/<name>.md`. Run one winning persona per name; do not move existing repository overrides.

### Read the finding format

Read `~/.agent-skills/skills/plan-review/references/plan-finding-format.md` — include its full content in each agent prompt.

### Read project instructions

Read applicable `AGENTS.md`, legacy `CLAUDE.md`, and `.agents/rules/` / `.claude/rules/`; reviewers need project conventions. Deduplicate linked copies.

### Spawn all reviewers in parallel using the medium model tier

Each agent prompt:

> "You are a plan reviewer. Read your reviewer persona below, then review the implementation plan provided.
>
> **Your reviewer persona:**
> [paste full contents of the agent's .md file, excluding the `always: true` frontmatter line]
>
> **Plan finding format** (you MUST use this format for all findings):
> [paste full contents of plan-finding-format.md]
>
> **Project conventions:**
> [paste applicable project instructions, or state that none were found]
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

Collect all findings from all reviewers. Save the full findings to disk (in `<work-folder>/reviews/`
as `<slug>.plan-review.<YYYY-MM-DD>.md`, creating the directory with `mkdir -p` if needed) for reference and session recovery. Then present findings
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
