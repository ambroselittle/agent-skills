# Take-Home Evaluation Criteria

What evaluators look for in take-home solutions. **Read this BEFORE planning, not just before shipping.** These criteria shape how to build — architecture, testing strategy, documentation, git history — not just what to verify at the end. Use it twice: once during planning to ensure the approach meets these standards, and again before shipping as a final checklist. Any gap found here is a gap the evaluator will find too.

## Completeness

**Importance: table stakes.** An elegant partial solution loses to a working complete one. Missing a stated requirement is usually disqualifying.

- [ ] Every stated requirement is addressed and demonstrably working
- [ ] Edge cases handled — not just the happy path
- [ ] Error states considered — what happens when things go wrong?
- [ ] **Bonus/stretch goals implemented** — with agentic development, there is almost never a reason to skip these. Bonus items exist because evaluators want to see them but didn't want to overwhelm human candidates with a huge required list. Treat them as required unless the stated time constraint is unusually tight (under 30 minutes) AND there are many bonus items. Completing bonus items is one of the easiest ways to stand out.

## Testing

**Importance: critical differentiator.** Having tests AT ALL sets you apart — many candidates skip them entirely. This is the single most common disqualifier after missing requirements.

- [ ] Unit tests cover business logic and core functions
- [ ] Integration or API tests cover endpoints (if applicable)
- [ ] Edge cases tested: empty inputs, invalid data, boundary conditions
- [ ] **E2E tests for every feature's happy path** (if there is a UI). Not just one smoke test — each user-facing feature should have at least one E2E test that walks through its primary flow. These prove the feature actually works end-to-end, not just that individual units pass in isolation. Use Playwright with Page Object Model for maintainability.
- [ ] Tests actually run and pass — not just stubs or skipped tests
- [ ] Test runner configured so `npm test` / `pytest` / equivalent just works
- [ ] E2E tests runnable via a single command (`npm run test:e2e` or similar)

## Code Quality

**Importance: high.** This is what evaluators read first. Sloppy code signals sloppy thinking.

- [ ] Clean, readable, idiomatic for the language and framework
- [ ] Well-structured: logical file organization, separation of concerns
- [ ] Consistent naming conventions throughout
- [ ] No dead code, no commented-out blocks, no debugging artifacts (`console.log`, `print`, `TODO`)
- [ ] Error handling where appropriate — input validation, edge cases, graceful failures

## Architecture

**Importance: moderate to high.** This is a take-home, not a production codebase — but the evaluator is assessing whether you *think* at a senior+ level. Don't optimize for "simplest thing that works for this small project." Demonstrate that you know how to structure real software, even at small scale. A clean service layer in a CRUD app isn't over-engineering — it's showing you understand separation of concerns. A repository pattern for a todo API isn't overkill — it's showing you'd scale well on their team. The line to avoid is *pointless abstraction* (plugin architectures, event buses, factory factories) — not *good structure*.

- [ ] Separation of concerns where it matters: business logic separated from HTTP handling, domain boundaries clear between modules. But don't add layers just for layers' sake — every layer must solve a real problem (testability, complexity management, genuine swappability). See `design-philosophy.md` for the full perspective.
- [ ] Domain-oriented structure: code grouped by what it does (todos, auth, payments), not by technology (controllers, services, repositories). Related code lives together.
- [ ] Modularity — could the next feature be added without rewriting existing code? Structure for the next feature, not the tenth.
- [ ] Consistent patterns within the codebase — if one module has a service layer, they all should
- [ ] Evidence of intentional design decisions, not just "it works" — the evaluator should see choices that signal experience and judgment about when to add structure and when simplicity is the right call

## Documentation

**Importance: high.** The evaluator's first interaction is the README. If they cannot run the project in under two minutes, you have already lost points.

- [ ] README covers: what the project does, how to set it up, how to run it, how to test it
- [ ] Design decisions documented briefly — why you chose X over Y
- [ ] API documentation if there are endpoints (routes, request/response shapes)
- [ ] Inline comments only where logic is genuinely non-obvious
- [ ] Setup instructions actually work — run them yourself from a clean state
- [ ] **`CLAUDE.md`** at project root — orients AI agents (and humans) to the codebase: what the project does, how it's structured, key conventions, how to build/test/lint. This is the agentic equivalent of a good README and shows awareness of modern AI-assisted development workflows. Think of it as onboarding docs for the next developer, whether human or AI.
- [ ] **`.claude/rules/`** for non-obvious conventions — testing patterns, module boundaries, type conventions, anything an agent (or new team member) would get wrong without guidance. Keep rules focused and actionable, not aspirational.

## Git History

**Importance: moderate.** Evaluators read `git log`. Your commit history tells them how you think and work.

- [ ] Meaningful commits showing progression — not one giant commit
- [ ] Commit messages describe what changed and why
- [ ] Clean history — no "fix typo" chains, no merge commits pulled from main
- [ ] Progressive commits show thought process: scaffold, implement, test, refine

## Professional Extras

**Importance: differentiators.** None of these are required, but each one signals professional habits. They separate "gets the job done" from "would be great to work with."

- [ ] CI pipeline configured (GitHub Actions or similar) — shows automation mindset
- [ ] Linting and formatting configured and passing
- [ ] Type safety enabled (TypeScript strict mode, Python type hints, etc.)
- [ ] Docker setup for easy evaluation (`docker compose up` and it works)
- [ ] Environment variable handling: `.env.example` with documentation
- [ ] Pre-commit hooks or quality gates
- [ ] **Agentic scaffolding** — `CLAUDE.md` and `.claude/rules/` configured (see Documentation section). This signals that you build software with AI-assisted workflows in mind — an increasingly valued skill. A well-written `CLAUDE.md` also doubles as excellent developer onboarding documentation.

## Common Pitfalls

Flag if any of these are present in the solution:

- [ ] **Over-engineering** — complex abstractions, design patterns, or indirection layers for a simple problem
- [ ] **Under-engineering** — everything in one file, no structure, no separation
- [ ] **Missing requirements** — any stated requirement not addressed (re-read the prompt)
- [ ] **No tests** — even basic tests are better than none
- [ ] **Broken setup** — evaluator cannot run the project following the README instructions
- [ ] **Giant single commit** — "initial commit" with the entire solution shows no process
- [ ] **Leftover scaffolding** — boilerplate from generators that is unused or irrelevant
- [ ] **Hardcoded values** — secrets, paths, or config that should be environment variables
