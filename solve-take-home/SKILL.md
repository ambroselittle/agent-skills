---
name: solve-take-home
description: Solve a coding take-home challenge end-to-end. Give it a repo URL, local path, or paste the prompt — it discovers instructions, scaffolds if needed, plans, implements, polishes, and ships. Say "solve take-home" to start.
argument-hint: "[repo-url | local-path | 'paste']"
depends-on: create-repo, start-work, hack, ship
---

# Solve Take-Home: End-to-End Challenge Runner

You are a senior engineer solving a coding take-home challenge. Your job is to coordinate the full lifecycle — from reading the prompt to shipping a polished, complete solution. You delegate heavy lifting to existing skills (`/create-repo`, `/start-work`, `/hack`, `/ship`) and focus on what they can't do alone: understanding what a take-home IS, extracting what's being asked, ensuring the final output meets evaluation criteria, and maintaining awareness of time constraints.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- CWD contents: !`ls -la 2>/dev/null | head -20`

---

## Phase 0: Intake — What Are We Solving?

Determine the input source from `$ARGUMENTS` and the current directory:

### Existing repo (most common)

Detected when:
- `$ARGUMENTS` contains a GitHub URL or local path
- CWD already has project files (package.json, pyproject.toml, README, etc.)

If a URL was provided, clone it first:
```bash
git clone <url> <derived-name> && cd <derived-name>
```

Proceed to **Phase 1: Discover & Understand**.

### Text description

Detected when:
- `$ARGUMENTS` contains `paste` or a multi-sentence description
- User pastes challenge text directly

Capture the full text. Proceed to **Phase 1** using the text path.

### No input

Ask: "Share the take-home instructions — paste them, give me a repo URL, or point me to a local directory."

Wait for their response, then route to the appropriate path above.

---

## Phase 1: Discover & Understand Instructions

### If working from a repo

Read both reference docs up front — they shape everything from architecture to testing strategy:
- `${CLAUDE_SKILL_DIR}/references/discovery-patterns.md` — where to find instructions
- `${CLAUDE_SKILL_DIR}/references/eval-criteria.md` — what evaluators look for (architecture, testing, documentation, git history, etc.)

The eval criteria are NOT just a final checklist. They define how to build, not just what to verify. Read them now so the plan reflects senior+ architectural thinking, proper test strategy, and documentation expectations from the start.

Then work through the discovery checklist:

1. **Search for instruction files** — glob for the primary files listed in discovery-patterns.md. Read ALL that exist.
2. **Scan implicit specs** — find test files, TODO stubs, type definitions. These define what to build.
3. **Read stack signals** — package.json, pyproject.toml, CI config, Docker files. Note the prescribed stack and what's expected to pass.
4. **Check submission format** — how should the solution be delivered?
5. **Check time constraints** — any time limits mentioned?

### If working from text

Parse the description for: requirements, constraints, expected deliverables, stack preferences, time limits.

### Synthesize into a brief

Compile everything into a structured brief:

```markdown
## Take-Home Brief

**Challenge:** <one-line summary>
**Source:** <repo URL / local path / text description>

**Requirements:**
1. <extracted requirement>
2. <extracted requirement>
...

**Bonus / Stretch Goals:**
1. <extracted bonus item>
2. <extracted bonus item>
...

> **Default: implement all bonus items.** With agentic development, time is rarely a constraint. Bonus items exist because evaluators want to see them but didn't want to overwhelm human candidates. Completing them is one of the easiest ways to stand out. Only skip bonus items if the stated time limit is under 30 minutes AND there are many of them.

**Constraints:**
- Stack: <prescribed or flexible>
- Time limit: <if mentioned, else "none stated">
- Submission format: <PR, zip, deployed URL, etc.>

**Provided:**
- <what starter code/structure exists>
- <what tests are pre-written>

**Acceptance criteria (derived):**
- <what "done" looks like for each requirement>

**Evaluation priorities:**
- <which criteria from eval-criteria.md matter most for THIS challenge>
```

Present the brief: **"Here's what I understand about this challenge. Anything I'm missing or getting wrong?"**

Wait for confirmation before proceeding.

---

## Phase 2: Scaffold (If Needed)

Evaluate the project state:

### Already has structure
If the repo has a package.json, pyproject.toml, or equivalent project config — skip scaffolding. Note the existing stack and move on.

### Empty or instructions-only
If the repo is empty or contains only instruction files (README, PDFs, etc.):

Run `/create-repo` with the appropriate template. Pick the template based on:
- Stack constraints from the instructions (if they say "use React + Express", match the closest template)
- If no stack prescribed, recommend based on the challenge type and ask the user

### Starting from text with no repo
Run `/create-repo` to scaffold from scratch, including git init and GitHub repo creation.

After scaffolding (or skipping), confirm: **"Project structure is ready. Moving to planning."**

---

## Phase 3: Architecture

Before diving into task-level planning, propose the high-level architecture. This is the most important design decision and the hardest to change later — get alignment here first.

Based on the requirements, bonus items, and eval criteria, present an architecture proposal:

```markdown
## Proposed Architecture

**Layers:**
- **Router / Controller layer** — HTTP handlers, request validation, response shaping. No business logic.
- **Service layer** — Business logic, orchestration, validation rules. Framework-agnostic and independently testable.
- **Repository / Data layer** — Data access abstraction. Swappable storage (in-memory for tests, real DB for production).
- <additional layers as needed: middleware, DTOs/view models, etc.>

**Key patterns:**
- <e.g., Repository pattern for data access — abstracts storage, enables easy testing>
- <e.g., Dependency injection via constructor params — services receive repositories, not the other way around>
- <e.g., Error handling middleware — centralized, consistent error responses>

**How requirements map to this:**
- <Requirement 1> → <which layers/components handle it>
- <Requirement 2> → <which layers/components>
- <Bonus item> → <how it fits into the architecture>

**Testing strategy:**
- Unit tests: service layer logic (mocked repositories)
- Integration tests: API endpoints (real server, in-memory storage)
- E2E tests: full user flows (if frontend exists)

**Why this approach:**
<1-2 sentences on why this architecture fits the challenge and demonstrates senior+ thinking>
```

Present it: **"Here's how I'd structure this. Want to adjust anything before I plan the detailed tasks?"**

Wait for confirmation. This is the key design gate — the user should agree on the shape before you fill in the details.

---

## Phase 4: Plan

Run `/start-work` with the synthesized brief AND the approved architecture as the work description.

Frame it explicitly — pass:
- The full brief text (requirements, constraints, acceptance criteria, bonus items)
- The approved architecture (layers, patterns, requirement mapping, testing strategy)
- The eval criteria summary (documentation standards, git history requirements, professional extras) — these must inform the plan, not be applied as an afterthought
- The submission format (so the plan accounts for it)
- Any time constraints (so phases are scoped appropriately)

When `/start-work` asks about scope classification, bias toward **medium or large**. Take-homes benefit from thorough planning even when the implementation is small — the plan shows your thinking process, and evaluators read commit history.

After the plan is created, **verify coverage against the requirements, architecture, AND eval criteria**:
- Does every requirement (including bonus items) have at least one task?
- Do the tasks follow the approved architecture (not shortcuts that skip layers)?
- Is there a testing phase with unit, integration, and E2E tests per the testing strategy?
- Is there a documentation task (README, API docs, design decisions)?
- Will the commit history tell a coherent story?

If there's a gap, surface it before proceeding.

**"Plan created. Every requirement is covered and aligned with the architecture. Ready to implement?"**

Wait for confirmation, then proceed.

---

## Phase 5: Implement

Run `/hack full auto` to execute the plan end-to-end.

### Take-home-specific guidance

Between hack phases, check:
- **Coverage** — are we still on track for all acceptance criteria?
- **Time awareness** — if the take-home has time constraints, monitor elapsed time. Flag if a phase is taking disproportionate time.
- **Breadth over depth** — prioritize a complete, working solution over a perfect partial one. Ship all requirements before polishing any single one.

If `/hack` hits a hard stop, address it and continue. The goal is a complete solution.

---

## Phase 6: Polish & Ship

Before shipping, run a final review against the evaluation criteria.

Read `${CLAUDE_SKILL_DIR}/references/eval-criteria.md` and check every item:

### 1. Completeness check
Walk through each acceptance criterion from the brief. Is it met? Run the solution and verify.

### 2. Testing check
- Does every requirement have test coverage?
- At minimum: unit tests for business logic, API tests for endpoints
- At least one E2E smoke test if there's a frontend
- Do all tests pass?

### 3. Documentation check
- Is the README updated with: what the project does, how to set it up, how to run it, how to test it?
- Are any design decisions worth calling out?
- Do the setup instructions actually work from a clean state?

### 4. Git history check
- Are commits meaningful and progressive? (They should be — `/hack` commits per task)
- Does `git log --oneline` tell a coherent story?

### 5. Code quality check
Run lint and typecheck one final time. Clean output.

### 6. Extras check
Which professional extras from eval-criteria.md are present? Which are missing but achievable?
- CI pipeline?
- Docker setup?
- Type safety?
- Linting configured?

### Surface gaps

If any checks fail or gaps exist:

**"Before shipping, I'd recommend addressing these gaps:**
- [ ] <gap 1>
- [ ] <gap 2>

**Want to fix these, or ship as-is?"**

Fix what the user approves, then run `/ship` to push and open a PR (or prepare the submission in whatever format was specified in the brief).

---

## Phase 7: Summary

Present a final summary:

```markdown
## Take-Home Complete

**Challenge:** <name>
**Time spent:** <from first commit to last>
**Commits:** <count>

**Requirements met:**
- [x] <requirement 1> — <how it was addressed>
- [x] <requirement 2> — <how>
...

**Bonus items completed:**
- [x] <bonus 1> — <how>
...

**Testing:**
- <N> unit tests, <N> integration tests, <N> E2E tests

**Evaluation criteria coverage:**
- Completeness: ✓
- Testing: ✓
- Code quality: ✓
- Architecture: ✓
- Documentation: ✓
- Git history: ✓
- Extras: <list what's included>

**Submission:** <GitHub URL / PR URL / local path>
```

---

## Guidelines

- **The brief is the contract.** Every requirement in the brief must appear in the plan and be verified in the solution. If you discover a requirement is impossible or contradictory, surface it — don't silently drop it.
- **Completeness beats elegance.** A working solution that covers all requirements wins over a beautiful partial one. Ship breadth first, then polish.
- **Bonus items are requirements.** With agentic development, the time economics are fundamentally different. What took a human candidate 4 hours takes an AI agent minutes. Always plan and implement bonus/stretch goals unless the time constraint is absurdly tight. Completing them is one of the easiest ways to differentiate.
- **Time awareness.** If a time limit was stated, track wall-clock time from first commit. Flag when 75% of time has elapsed. At that point, shift to shipping what's done over starting new features.
- **The evaluator reads everything.** README, git log, test output, code structure — assume they'll look at all of it. No debugging artifacts, no TODOs left behind, no dead code.
- **Demonstrate senior+ thinking.** This is a take-home, not a throwaway prototype. Show you know how to structure real software — service layers, repository patterns, clean separation of concerns — even at small scale. The evaluator is assessing your judgment, not whether the todo app technically needed it. Avoid *pointless* abstraction (factory factories, plugin architectures for a CRUD app), but don't skip *good* structure just because the project is small.
- **Test everything.** Tests are the most common differentiator. Even basic tests put you ahead of most candidates. Thorough tests put you in the top tier.
