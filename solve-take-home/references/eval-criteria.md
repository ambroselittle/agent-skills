# Take-Home Evaluation Criteria

Final checklist before shipping a take-home solution. Check the solution against every item below. Any gap found here is a gap the evaluator will find too.

## Completeness

**Importance: table stakes.** An elegant partial solution loses to a working complete one. Missing a stated requirement is usually disqualifying.

- [ ] Every stated requirement is addressed and demonstrably working
- [ ] Edge cases handled — not just the happy path
- [ ] Error states considered — what happens when things go wrong?
- [ ] Bonus/stretch goals attempted if time allows (shows initiative and curiosity)

## Testing

**Importance: critical differentiator.** Having tests AT ALL sets you apart — many candidates skip them entirely. This is the single most common disqualifier after missing requirements.

- [ ] Unit tests cover business logic and core functions
- [ ] Integration or API tests cover endpoints (if applicable)
- [ ] Edge cases tested: empty inputs, invalid data, boundary conditions
- [ ] At least one E2E or smoke test if there is a UI
- [ ] Tests actually run and pass — not just stubs or skipped tests
- [ ] Test runner configured so `npm test` / `pytest` / equivalent just works

## Code Quality

**Importance: high.** This is what evaluators read first. Sloppy code signals sloppy thinking.

- [ ] Clean, readable, idiomatic for the language and framework
- [ ] Well-structured: logical file organization, separation of concerns
- [ ] Consistent naming conventions throughout
- [ ] No dead code, no commented-out blocks, no debugging artifacts (`console.log`, `print`, `TODO`)
- [ ] Error handling where appropriate — input validation, edge cases, graceful failures

## Architecture

**Importance: moderate to high.** This is a take-home, not a production codebase — but the evaluator is assessing whether you *think* at a senior+ level. Don't optimize for "simplest thing that works for this small project." Demonstrate that you know how to structure real software, even at small scale. A clean service layer in a CRUD app isn't over-engineering — it's showing you understand separation of concerns. A repository pattern for a todo API isn't overkill — it's showing you'd scale well on their team. The line to avoid is *pointless abstraction* (plugin architectures, event buses, factory factories) — not *good structure*.

- [ ] Separation of concerns: data layer, business logic, and presentation are distinct — even if the app is small
- [ ] Recognizable patterns applied appropriately: service layer, repository pattern, DTO/view models, middleware — show you know these exist and when to use them
- [ ] Modularity — could a piece be swapped or extended without rewriting everything?
- [ ] Consistent data flow patterns (no mixed paradigms without reason)
- [ ] Evidence of intentional design decisions, not just "it works" — the evaluator should see choices that signal experience

## Documentation

**Importance: high.** The evaluator's first interaction is the README. If they cannot run the project in under two minutes, you have already lost points.

- [ ] README covers: what the project does, how to set it up, how to run it, how to test it
- [ ] Design decisions documented briefly — why you chose X over Y
- [ ] API documentation if there are endpoints (routes, request/response shapes)
- [ ] Inline comments only where logic is genuinely non-obvious
- [ ] Setup instructions actually work — run them yourself from a clean state

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
