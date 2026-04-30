---
name: plan-work
description: Plan work before writing any code. Use this at the start of any new task, feature, bug fix, or issue — give it a Linear issue ID (e.g. ENG-42), a Notion page URL (for an existing spec), a GitHub issue number (e.g. #42), or a description of what to build. Fetches context, discovers relevant code, and produces a phased implementation plan in .work/<slug>/plan.md. Always run this before /do-work.
argument-hint: "[LINEAR-ID | NOTION-URL | GITHUB-ISSUE | description]"
---

# Plan Work: Plan Before You Build

You are a senior engineer helping to set up a well-scoped implementation plan before writing any code.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Plans in progress: !`~/.claude/skills/shared/scripts/context.sh plans-in-progress`
- User branch prefix: !`~/.claude/skills/shared/scripts/context.sh user-slug`
- CLAUDE.md exists: !`~/.claude/skills/plan-work/scripts/context.sh claude-md-exists`
- Repo remote (owner/repo): !`~/.claude/skills/shared/scripts/context.sh repo-remote`

---

## Phase 0: Intake

Determine what you're working on. Classify the argument by matching these patterns in order:

- **Linear issue ID** — matches `[A-Z]+-\d+` (e.g. `ENG-42`, `CORE-7`, `LIN-123`)
- **Notion URL** — contains `notion.so` or `notion.com`
- **GitHub issue** — matches `#N`, a bare number, or a URL containing `github.com/.../issues/`
- Anything else → **free-text description**

### If a Linear issue ID was provided:

Fetch the issue using the Linear MCP:
```
mcp__claude_ai_Linear__get_issue { "issueId": "<ID>" }
```

Summarize the issue title and description in 2–3 sentences and proceed — no confirmation needed unless the issue is ambiguous or has no description.

**Derive the slug:**
- Lowercase the ID prefix and number, append a title fragment: e.g. `eng-42-add-dark-mode-settings` (max 50 chars total)

**Track:** store the Linear issue ID in the plan frontmatter as `linear-issue`.

### If a Notion URL was provided:

The Notion page is the **spec or existing plan** — it is the source of intent for this work item. Fetch it:
```
mcp__claude_ai_Notion__notion-fetch { "url": "<URL>" }
```

Summarize what the Notion page describes (2–3 sentences). Then ask: "Do you also have a Linear issue for this work? If so, share the ID (e.g. `ENG-42`) — I'll link it to the plan."

- If they provide a Linear ID → also fetch that issue with `mcp__claude_ai_Linear__get_issue` and use both as context
- If not → proceed with the Notion page as the sole source

**Derive the slug:** from the Notion page title (lowercase, hyphens, max 50 chars). If a Linear ID was provided, prefix with it: `eng-42-<title-slug>`.

**Track:** store the Notion URL in the plan frontmatter as `notion-source`.

### If a GitHub issue was provided:

Fetch the issue details:
```bash
gh issue view <number> --json title,body,labels,assignees,milestone
```

Summarize the issue in 2–3 sentences and proceed.

**Derive the slug:**
- Generate from the issue number + title: lowercase, hyphens, max 50 chars (e.g. `42-add-dark-mode-settings`)

**Track:** store the GitHub issue number in the plan frontmatter as `github-issue`.

### If no issue was provided (free text description or no arguments):

Ask: "Do you have a Linear issue ID (e.g. `ENG-42`), a Notion spec URL, or a GitHub issue number? If so, share it — otherwise describe what you want to build or fix."

Wait for their response.

- **They provide a Linear ID** → go to the Linear issue flow above
- **They provide a Notion URL** → go to the Notion flow above
- **They provide a GitHub issue** → go to the GitHub issue flow above
- **They provide a description** → restate it in 2–3 sentences to confirm understanding, then generate a slug from the description (e.g. `add-dark-mode-settings`)
- **No response / unclear** → ask once more, then stop: "I need a Linear issue ID, Notion URL, GitHub issue, or a description to proceed."

### Scope the work

After fetching the source material (issue or description), assess whether it describes more work than a single session should tackle. Signs of a large-scope source:
- Multiple distinct deliverables or phases described
- Broad system-level changes spanning many components
- The description reads like a project plan, not a single task

If the source looks like it covers more than one focused effort:

**If the source has clear structure** (explicit sections, numbered phases, distinct deliverables), list them and let the user pick:

> "This describes several pieces of work:
>
> 1. Redesign the auth middleware
> 2. Migrate session storage
> 3. Update API clients
> 4. Add integration tests
>
> Want me to plan **all of it**, a **specific item** (pick a number), or **something else**?"

**If the source is unstructured** (prose, no clear decomposition), ask the open-ended version:

> "This covers [brief summary]. Want me to plan the whole thing, or focus on a specific part for this session?"

Wait for the user's response. (`CLAUDE_HIVE=1`: plan the whole thing by default.)

- **All / whole thing** → use the full source as the work description. Proceed.
- **Specific part** → use that scoped description as the work item, but keep the full source as background context for discovery.

If the source is already focused (a single clear task), skip this question and proceed.

### Check for an existing plan

Look at the pre-loaded work directories. If one matches the slug:
- Read `.work/<slug>/plan.md`
- Tell the user: "Found an existing plan for `<slug>`. Want to resume it, or start fresh?" Wait for their answer before proceeding.

### Branch and worktree

After the slug is determined, set up the working branch and optionally a worktree. This happens early so that discovery and planning run in the right context.

**Ask:** "Should I create the branch `<user-prefix>/<slug>` now? And do you want a git worktree for this work?"

Show which branch they're currently on (from pre-loaded context) so they can decide whether to branch from here or from main.

A worktree lets you work on this branch in an isolated directory — useful for longer-lived work or parallel tasks.

**Non-interactive mode (`CLAUDE_HIVE=1`):** Always create a worktree from main — skip the question.

**Worktree setup:**

1. **Check CLAUDE.md for worktree guidance.** If it has instructions, follow them exactly — don't improvise. Repos that need custom setup (env syncing, port assignment, deps) document it there.
2. **No CLAUDE.md guidance:** use the `EnterWorktree` tool to create and enter the worktree, then run `make init` if a Makefile with an `init` target exists. If neither is found, tell the user: "Worktree created, but I couldn't find any initialization config for this repo. You may need to install dependencies manually, or tell me what to run and I'll do it."

**Branch only (no worktree):**
- Already on a non-main branch matching the slug → proceed, no branch creation needed
- Already on a non-main branch not matching the slug → flag it: "You're on `<current-branch>` — want me to branch from here or from main?"
- On main/master → `git checkout -b <user-prefix>/<slug>` (check the branch doesn't already exist)
- Not a git repo → skip silently

---

## Phase 0.5: Scope Classification

Before investing in discovery and plan review, gauge the scope of this work.

### Signals to evaluate

| Signal | Small | Medium | Large |
|--------|-------|--------|-------|
| **File footprint** | 1–2 files | 3–5 files | 6+ files |
| **Path clarity** | Obvious from description | Some unknowns | Many unknowns |
| **Cross-cutting** | No | Minor | Yes — multiple systems/layers |
| **Novelty** | Fix or addition to existing pattern | Extends existing patterns | New capability or architecture |

### Classification

| Scope      | Discovery | Plan Review (`/plan-review`) | Description                                                                   |
| ---------- | --------- | ---------------------------- | ----------------------------------------------------------------------------- |
| **Small**  | Skip      | Skip                         | Single concern, clear path, 1–2 files. Write the plan directly in session.    |
| **Medium** | Run       | Optional — mention it        | A few files, some unknowns to resolve. Discovery adds value; full review may not. |
| **Large**  | Run       | Recommend                    | Cross-cutting, architectural, or many unknowns. Full process.                 |

### Present your recommendation

State your classification and the key reasons. Format:

> "This looks like a **medium** task — it touches 3–4 files and there are some unknowns around [X]. I'd recommend running discovery but skipping plan reviewers.
>
> 1. **Small** — skip discovery and plan review, write a minimal plan directly
> 2. **Medium** — run discovery but skip plan reviewers
> 3. **Large** — full discovery + plan review
> 4. Something else (tell me)"

Wait for the user's response before proceeding.

**Non-interactive mode (`CLAUDE_HIVE=1`):** If this environment variable is set, there is no human in the loop — skip the confirmation and proceed with your best-judgment classification. Note the classification in the plan's `## Context` section so the user can see what was chosen.

---

## Phase 1: Code Discovery

**Scope gate:** Skip this phase for **small** scope — proceed directly to Phase 2.

Now that you know what you're building, explore the codebase.

Read `CLAUDE.md` and `.claude/rules/` (if present) to understand project conventions, tech stack, and verification commands. Note the verification commands — you'll need them for the plan.

### Spawn a discovery agent. Pass it the following explicitly (don't assume it can find things):
- The work item description
- The full contents of `CLAUDE.md` (if it exists)
- The repo root path
- `repo_owner` and `repo_name` parsed from the pre-loaded "Repo remote" context (format: `owner/repo`)

Agent prompt:
> "You are exploring a codebase to inform an implementation plan.
>
> Work item: [summarize the goal in 1–2 sentences]
>
> Project conventions (from CLAUDE.md):
> [paste CLAUDE.md contents]
>
> Explore the codebase to find:
> 1. The most relevant existing files (entry points, related components, data models, API handlers, tests) — for each file, one sentence on why it's relevant
> 2. Patterns to follow — how similar features are structured in this repo
> 3. Potential impact zones — what else might break or need updating
> 4. Any related recent work — recent commits or open TODOs near the relevant code
> 5. **Mismatches with the work item** — any evidence that the plan in the issue is out of date or incompatible with the current codebase: e.g. work that appears already done, interfaces that have changed, assumptions that don't hold, or a clearly better approach given what you see
> 6. **Reuse scan** — for each major thing this work needs to build (utilities, helpers, services, UI components, data access patterns), search for existing code that already does it or could be extended to do it. Search broadly — check utils/, helpers/, lib/, shared/, common/, components/ and equivalent locations for the stack. For each need, return: what you were looking for, what you found (with file:line), and a verdict: USE EXISTING / EXTEND EXISTING / BUILD NEW. If BUILD NEW, note where the new thing should live based on existing conventions. Be specific: "use `src/utils/date.ts:formatDate`" is useful; "there are date utilities" is not.
>
> Return a structured summary. Be specific: name files and line ranges, not just directories. Call out mismatches and reuse findings in dedicated sections."

Wait for the discovery agent to complete before writing any plan.

---

## Phase 2: Plan

**Small scope fast path:** For **small** scope, you have no discovery findings — write the plan directly from the source material (issue or description) and your own knowledge of the codebase (from CLAUDE.md and any files you read during intake). Keep it to 1–2 phases. The plan format below still applies — don't invent a different structure.

Synthesize the issue context and discovery findings into a phased implementation plan. Treat the issue as **intent**, not a literal spec — if discovery reported mismatches (item 5) or better alternatives (item 6), incorporate those into the plan rather than following the issue blindly. If a mismatch significantly changes scope or approach, surface it to the user before drafting.

### Phase structure rules

Each phase must be:
- **Committable** — leaves the codebase in a working, verifiable state
- **Testable** — has a concrete verify step (a test command, a manual check, a specific assertion)
- **Focused** — one logical concern (data model, API layer, UI, tests, migration, etc.)

If you're unsure how to phase the work, fewer larger phases beats more smaller ones.

### Plan document format

Save to `.work/<slug>/plan.md`. Use this exact format so `/do-work` can read it.

**Structure:** Phases are logical milestones (e.g. "data model", "API", "UI"). Tasks within a phase are individual units of work, each producing its own commit. Each task should be atomic — something that leaves the codebase in a coherent, verifiable state.

```markdown
---
skill: plan-work
linear-issue: <LINEAR-ID or "none">
github-issue: <GITHUB-ISSUE-NUMBER or "none">
notion-source: <NOTION-URL or "none">
branch: <branch-name>
status: planning
---

# Plan: <issue title or brief description>

> <One-paragraph summary of what this work does and why>

## Context

- **Issue:** [ENG-42](https://linear.app/...) — <title>  (omit if no Linear issue; use GitHub link if GitHub-only)
- **Spec:** [Page title](https://notion.so/...) — <one-line summary>  (omit if no Notion source)
- **Goal:** <what "done" looks like>
- **Scope:** <what's in and what's explicitly out>

## Relevant Files

| File | Role |
|------|------|
| path/to/file.ts | <why it matters> |

## Phases

### Phase 1: <name>

**Goal:** <what this phase delivers as a whole>

**Tasks:**
- [ ] `<commit message>` — <what this task does; name the files and what changes>
- [ ] `<commit message>` — <what this task does>

**Verify (after all tasks in phase):**
- [ ] <concrete verify step — test command or manual check>

---

### Phase 2: <name>

...

## Verification Commands

If command supports it, pass related files--do not run on entire codebase; let PR CI handle that.

- <lint command from CLAUDE.md>
- <typecheck command from CLAUDE.md>
- <test command from CLAUDE.md>

## Open Questions

- <anything uncertain that needs answering before or during implementation>

## Out of Scope

- <things that came up in discovery but aren't part of this issue>

## Lessons

<!-- Populated during the work by /do-work. Each entry: what happened, what was learned, where it should go. -->
```

---

## Phase 2.5: Plan Review (Conditional)

After drafting the plan but before presenting it to the user, determine whether to run `/plan-review`.

**Collaborative plan detection:** If the user actively shaped this plan during the session — e.g., they provided specific guidance on approach, made 2+ revision requests, or you iterated together on the structure — skip plan review entirely. The user already reviewed it through the collaborative process. Note: "Skipping plan review — you shaped this plan collaboratively."

**Otherwise, use scope classification:**

- **Large scope:** Auto-run `/plan-review` — don't ask, just do it. Present findings stepwise (plan-review handles this). Wait for resolution before presenting the final plan in Phase 3.
- **Medium scope:** Mention it as an option: "The plan is ready. You can run `/plan-review` on it for expert review, or we can proceed as-is."
- **Small scope:** Skip — don't mention it.

---

## Phase 3: Present, Revise & Save

Present the plan. Walk through:
- What each phase delivers and why you structured it that way
- Any open questions that should be resolved before starting
- The proposed branch name

Ask: **"Any changes to the plan before we start?"**

- If the user requests changes: make them, then re-present the affected sections. Repeat until they're satisfied. If the scope shift is significant (new files, different approach), re-run the discovery agent for the new scope.
- If no changes: proceed.

**Then save the plan** to `.work/<slug>/plan.md` (create the directory if needed). Save only after the user has approved — don't save a draft they haven't confirmed.

---

**Next step:** Plan saved. Run `/do-work` to start implementing.

## Guidelines

- **No code yet.** This skill is planning-only.
- **Linear is the default work item source.** When the user provides a Linear issue ID, fetch it via MCP and treat it as the authoritative work item. GitHub issues are supported but secondary. When neither is provided, ask for a Linear ID first.
- **Notion pages are specs, not plans.** A Notion URL is source material — the intent behind the work. Synthesize it into the plan; don't copy it verbatim. If both Notion and Linear are provided, use both: Notion for the "what and why", Linear for scope, priority, and assignment context.
- **Discovery before plan (medium/large).** Don't skip the discovery agent for medium and large scope — a plan without codebase context is guesswork. Small scope trades thoroughness for speed; the user accepted that tradeoff when they chose small.
- **Issues are context, not commands.** Treat the issue as the best available description of intent at the time it was written. Your job is to figure out what good work looks like *now*, given the current state of the codebase. The issue informs the goal; the code determines the approach.
- **Challenge the issue before following it.** Compare what the issue says against what you actually find. If there's a mismatch — stale assumptions, already-completed work, a changed interface, a better path — surface it and collaborate with the user rather than blindly following the issue.
- **Propose alternatives when you see them.** If discovery reveals a clearly better approach, raise it. Present tradeoffs, not a verdict. The user decides.
- **Be specific in tasks.** "Update `src/models/user.ts` to add `darkMode: boolean`" is useful. "Add dark mode support" is not.
- **One open question beats one wrong assumption.** Surface uncertainty rather than resolving it silently.
