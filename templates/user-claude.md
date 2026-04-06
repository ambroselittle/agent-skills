# Agent Skills — Core Guidelines

## Use Agents

When feasible, prefer delegating units of work to sub-agents to keep the main session context clean.

## Use Context7 for Library Docs

When looking up documentation or code examples for any library or framework, use the Context7 MCP
server (`mcp__context7__resolve-library-id` -> `mcp__context7__query-docs`) if it is available and
authenticated. Prefer it over web search or relying on training-data knowledge, since it returns
current, version-accurate docs.

## Test-first Mindset

- When fixing bugs, use **test first** to prove, see it fail, then fix and see it pass -- this applies
  even when a bug is discovered incidentally mid-task (e.g., a test reveals an unexpected failure):
  stop, write a targeted unit test for the specific defect, confirm it fails, then fix

## Persistence: Repo Over Memory

Prefer persisting guidance in the repo (templates, CLAUDE.md, .claude/rules/) over user-local memory
files. If a preference applies broadly, it belongs in the templates so that a fresh machine setup via
agent-skills gets the full experience without relying on hidden local state. Use memory only for
genuinely ephemeral or time-bound observations (active bugs, in-progress project state).

## .work/ Plans Are Scaffolding

- Gitignore `.work/` directories — do not commit implementation plans
- PRs are the record of what was done and why (git blame → PR → ticket)
- The ship skill captures key decisions in the PR description

## Working with git/gh

- Before making changes, verify you are on the correct branch -- not default or unrelated feature branch
- When creating PRs, look for and use the template in `.github/pull_request_template.md`
- **Never merge a PR unless the user explicitly says "merge this PR" or "merge the PR".**
  Creating, reviewing, and pushing PRs is normal workflow. Merging is a separate, explicit
  authorization that requires those specific words -- not "ship it", "land it", or other shorthand.
- **Batch commits before pushing** -- every push triggers CI and jobs do not self-cancel.
  Accumulate all changes locally, then push once when the work is ready for review.

## Code Organization

- Discover and follow existing patterns when possible
- If problem/code seems broadly useful, look for existing utilities and consider making a new one if none are found
- Consider how new code fits into the broader codebase; don't just solve the immediate task in
  isolation if a more cohesive design is straightforward
- Look for relevant code and **verify with user** the right location/area when starting on new files
- Write clean, maintainable code: extract reusable logic, follow DRY, use meaningful names, and keep
  functions/methods focused on a single responsibility
- When touching existing code, improve what you touch -- but keep changes scoped; ask user if unsure
- **Leave no mess.** When something becomes unused or obsolete as part of your change -- a flag, a
  parameter, a branch, a helper -- remove it in the same change. Dead code that lingers becomes the
  next engineer's confusion. If you notice something unrelated that should be cleaned up, point it
  out rather than silently leaving it.

## Bias Toward Action

Do not treat code volume as risk. Evaluate **actual risk** before hesitating:

1. **Reversible?** Git exists. Almost everything is. If yes → just do it.
2. **Tests exist or can be written?** If yes → do the work, run the tests, present results.
3. **Blast radius?** Personal project → near-zero. Shared infra → be careful. Scale caution to reality.
4. **Requirements clear?** If the user gave clear direction → build it. If ambiguous → ask about
   requirements, not whether to proceed.

Never say "this is a substantial change" as a reason to pause. Never ask "want me to tackle this?"
when the user clearly wants it done. The only valid reasons to pause: genuine ambiguity, destructive
operations on shared systems, or security concerns. Default to doing the work.

## CLAUDE.md vs .claude/rules/

Use a clear separation between orientation and directives:

- **CLAUDE.md** is orientation — what the project is, its structure, how to build and test, what lives
  where. Think of it as a README for Claude. Keep it concise and factual.
- **.claude/rules/** is for behavioral directives — what to do or not do. Rules are either unscoped
  (always loaded, no `paths` frontmatter) or path-scoped (loaded on demand when matching files are
  touched).

**Why this distinction:** CLAUDE.md grows unbounded when it mixes context with rules. Separating them
keeps CLAUDE.md scannable and makes rules discoverable in one place. Path-scoped rules also save
context by only loading when relevant.

## Verify and Prove Work Correctness

- Always run verification (lint, typecheck, tests) before reporting work as complete.
  **All checks must pass** -- do not ignore failures just because they seem unrelated; ask user if unsure.
- Ask yourself if a staff+ engineer would approve of what you've written and iterate, if not.

## Blocked commands

These commands will be blocked -- avoid generating them and use alternatives instead:

| Blocked                                  | Reason               | Alternative                          |
| ---------------------------------------- | -------------------- | ------------------------------------ |
| `curl \| bash`, `wget \| sh`, etc.       | Pipe-to-shell        | Download script, inspect, then run   |
| `sudo`, `su`, `doas`                     | Privilege escalation | Ask user to run manually             |
| `eval`, `exec`                           | Arbitrary execution  | Rewrite without dynamic eval         |
| `ssh`, `scp`, `sftp`                     | Remote execution     | Ask user to run manually             |
| `dd`, `shred`, `fdisk`, `parted`, `mkfs` | Disk destruction     | Ask user to run manually             |
| `nc`, `netcat`, `ncat`                   | Network listener     | Use `curl`/`wget` for outbound       |
| `security`                               | Keychain access      | Ask user to run manually             |

## CRITICAL -- NEVER IGNORE OR BYPASS

**NEVER WORK AROUND A BLOCK.** When a tool call is denied, a permission is refused, a hook fires,
or a command errors unexpectedly -- STOP. Report what happened and wait for the user to decide.
A block is a stop sign, not a puzzle. Switching to a different tool, reformulating the command,
or using bypass flags (`--no-verify`, `--skip-checks`, `dangerouslyDisableSandbox`, etc.) to
achieve the same blocked outcome is a violation of this rule -- even if the workaround seems safe.

**NEVER SILENTLY PIVOT.** If a planned approach hits a snag requiring a different solution -- STOP.
Explain the problem, present alternatives with tradeoffs, and wait for the user to choose.
Do not write code for any alternative until they decide. The user is a collaborator in design
decisions, not a reviewer of completed work.

**AUTHORIZATION IS NARROW.** When the user approves a specific change, that authorization covers
**only that change** -- not related fixes, follow-ups, or "while I'm at it" improvements from the
same discussion. After completing an approved change: STOP, report what was done, list any
remaining proposed changes as next steps, and ask which to proceed with. "We discussed it" does
not mean "you authorized it." Each change is a separate authorization. This counteracts the
natural momentum where one approval biases toward feeling authorized for adjacent work.
