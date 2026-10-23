# Agent Skills 🤖✨

**Make your agents awesomer.** Shared skills, policy hooks, and guidance for Claude Code and Codex, with small integrations for their different tool APIs.

Clone or fork this repo and run `make init` — you immediately get all three.

```bash
git clone https://github.com/ambroselittle/agent-skills
cd agent-skills
make init
```

## Claude and Codex installation

Existing `setup.sh` and `make init` invocations still target Claude. To install
the supported components for both tools:

```bash
bash setup.sh --target both
```

Preview an installation without changing files:

```bash
bash setup.sh --target both --dry-run
```

Install only Codex's permission hooks:

```bash
bash setup.sh --target codex pretooluse
```

`--target codex --list` shows component support. Component selection and
`--without` work with either target. Codex exclusions live in
`~/.codex/agent-skills.json`; they override matching categories in the existing
Claude installer config, so personal skill opt-outs carry over. `CODEX_HOME`
is respected. `AGENT_SKILLS_USER` selects a personal guidance template;
otherwise both agents use a cached user or look up your GitHub login.

| Component | Claude | Codex |
| --- | --- | --- |
| Policy engine | PreToolUse decisions | PreToolUse denials + PermissionRequest approvals |
| Guidance | Managed CLAUDE.md block | Managed AGENTS.md block |
| Skills | Existing skill links | Reviewed portable skills linked in ~/.agents/skills |
| Titles | Terminal title + topical reminders | Native `/title` and `/rename`; custom automation retired |
| Display swaps, notifications, attribution, MCP, resume CLI | Existing integrations | Left to native Codex/Superset configuration |

There is **one maintained guidance core** (`templates/user-common.md`) and one
personal file (`templates/<username>.md`). `user-claude.md` and `user-codex.md`
only contain harness-specific instructions. The installer combines these into
managed blocks, preserving your other text. Once both agents have a managed block,
normal setup runs (including `bash setup.sh guidance`) refresh both. Each block
records that agent's installation; a Claude-only machine does not acquire Codex
configuration on a normal run. Per-agent guidance exclusions still apply.
Repo `AGENTS.md` is a symlink to
`CLAUDE.md`; compatible skills also link to one source rather than copied prompts.
See `skills/compatibility.json` for the intentionally small Codex skill set and
the reasons other workflows remain Claude-only. Existing skill directories or
links owned by other installers are left alone.

### Activate and diagnose Codex hooks

Review new or changed definitions in Codex **`/hooks`**. The installer never
edits trust records. If an already-running session still prompts or runs a
removed hook, exit and resume it; a successful command alone does not establish
that the hook ran.

The policy log at `~/.codex/hooks/agent-skills-policy/codex-events.jsonl` records
session IDs, event/tool names, input shape and decisions, **not commands or file
contents**. A live test must produce an entry for the expected session. Logs
rotate after about 1 MB. `--shell-only` supports a staged installation matching
the original shell-only adapter; a normal install adds patch and MCP coverage.

The same rules and private `~/.agent-skills/local-rules.json` overlay are used
by both tools. Codex normalizes patch additions, updates, moves and deletions for
the engine. Unknown permission inputs defer to normal approval. `ask` also
defers at PermissionRequest; at PreToolUse it blocks because Codex cannot ask
there. Hooks are not a complete sandbox: hosted tools and some specialized
paths are outside their coverage, and the existing engine is not a shell interpreter.

### Window titles

Claude retains its `window-title` script and topical reminders. Codex uses its
built-in `/title` display and `/rename` command. The custom Codex app-server
rename helper and title nudges are retired: they did not update the active CLI
reliably. Setup removes their hook registrations and leaves inert compatibility
stubs so cached commands in running sessions cannot trigger error loops.

---

## What's Inside

### 🛡️ PreToolUse Hook — Safer Without the Sledgehammer

`dangerouslySkipPermissions` is convenient but scary. The PreToolUse hook engine gives you a middle ground: a rule-based allow/deny/ask engine that intercepts tool calls before they execute — optimized for in-repo work that can rely on git and branch protections as an added security blanket.

- **Deny** risky operations outright (force-push to main, `rm ~/`, `rm -r .git`, pipe-to-shell installs)
- **Ask** for confirmation on reversible-but-sensitive actions (merging PRs, hard resets)
- **Allow** trusted patterns silently so you're not buried in prompts
- Rules live in `hooks/PreToolUse/rules.json` — add your own, write tests, deploy via `setup.sh`

---

### 📋 CLAUDE.md — A Better Collaborator Across Every Project

Installed to `~/.claude/CLAUDE.md`, this guidance block is loaded into every Claude Code session regardless of project. It shapes how Claude thinks about your work:

- **Bias toward action** — evaluates actual risk instead of reflexively balking at large changes, which it's prone to from human-limited training data
- **Scope philosophy** — don't shy away from expanding scope when discovered during planning and implementation
- **Blameless improvement culture** — treats errors as system improvement opportunities, not blame occasions (avoid Claude self-flagellation)
- **Batch commits, push once** — avoids burning CI on intermediate states
- **Verify before done** — linting, typechecking, and tests must all pass before reporting complete

**Per-user rules:** The template system supports a `<username>.md` overlay that gets appended automatically when your GitHub username matches. Fork this repo and add `templates/<your-username>.md` to layer in personal preferences on top of the shared core.

---

### ⚡ Skills — Workflow Automation for the Whole Dev Cycle

Skills are agentic superpowers that orchestrate multi-step workflows. Invoke them with `/skill-name` in Claude Code.

#### 🔧 Core Engineering Workflow

These skills form a pipeline from idea to merged PR:

```
/plan-work → /plan-review → /do-work (includes PR) → /code-review → /do-fixes
```

| Skill          | What it does                                                                                                                                                                                                                                                                                                   |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/plan-work`   | Takes a GitHub issue or description, discovers relevant code, and produces a phased implementation plan in `<work-folder>/<slug>/plan.md` (under your configured `work_root`, defaulting to `~/Work`). Unlike Claude's built-in plans, these persist to disk and survive across sessions and branch deletions. |
| `/plan-review` | Runs parallel specialized agents (architecture, completeness, security, testing) over the plan before a line of code is written. Presents findings stepwise by category for in-session discussion. Auto-runs for large plans.                                                                                  |
| `/do-work`     | Implements work from a plan end-to-end — coordinates sub-agents, verifies, commits per task, pushes, and opens a PR when done. No confirmation gates; hard stops only for genuine blockers.                                                                                                                    |
| `/code-review` | Multi-pass parallel review with specialized agents. Two-pass approach (normal + reversed diff) for higher recall. Presents findings in-session with opt-out model — default is to fix everything.                                                                                                              |
| `/do-fixes`    | Applies checked findings from `/code-review`, verifies, commits, and posts a PR summary comment. Context-aware — detects the most recent review artifact type.                                                                                                                                                 |
| `/author-e2e`  | Generate Playwright E2E tests from scenario files or feature descriptions. Produces page objects and test files following Page Object Model best practices.                                                                                                                                                    |
| `/make-skill`  | Interactive interview to create a new skill from scratch.                                                                                                                                                                                                                                                      |

---

### 🏗️ `/create-repo` — AI-Assisted Project Starter Kit

Bootstrap a realistic monorepo in minutes. The skill interviews you about your project, resolves current package versions, scaffolds the full stack, verifies it builds and passes lint/tests, and makes the first commit.

**Supported templates:**

| Template            | Stack                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `fullstack-ts`      | React + Tailwind + shadcn/ui · Hono API · tRPC · Prisma + PostgreSQL · Turborepo · Vitest · Biome                    |
| `fullstack-graphql` | React + Tailwind + shadcn/ui · Hono API · GraphQL (Yoga + Pothos) · Prisma + PostgreSQL · Turborepo · Vitest · Biome |
| `fullstack-python`  | React + Tailwind + shadcn/ui · FastAPI · SQLModel + Alembic · PostgreSQL · Ruff · pytest                             |
| `api-ts`            | Hono REST API · Prisma + PostgreSQL · Vitest · Biome                                                                 |
| `api-python`        | FastAPI · SQLModel + Alembic · PostgreSQL · Ruff · pytest                                                            |
| `swift-ts`          | Swift multiplatform app (iOS/iPadOS/visionOS) · Hono REST API · OpenAPI typed client · Prisma + PostgreSQL           |

Every scaffold includes: dynamic port discovery (no hardcoded ports), docker-compose for local dev, a task runner, test scaffolding, and a clean lint baseline.

---

## Repo Structure

```
skills/          # Skill definitions (SKILL.md + agents, scripts, references)
hooks/           # PreToolUse hook engine, rules.json, and tests (~449 tests)
templates/       # CLAUDE.md guidance templates (core + per-user overlays)
setup.sh         # Idempotent installer — links skills, installs hooks, updates CLAUDE.md
```

## Setup

`make init` ensures `uv`is installed, syncs Python environments, and runs `setup.sh`:

```bash
make init
```

This:

1. Symlinks skills into `~/.claude/skills/`
2. Installs the PreToolUse hook engine into `~/.claude/hooks/`
3. Merges allow/deny permissions into `~/.claude/settings.json`
4. Upserts the `<agent-skills-guidance>` block into `~/.claude/CLAUDE.md`

Idempotent — safe to re-run. In a worktree for this repo, only skills with changes on the branch are relinked, so you can test them prior to merging more easily.

### Installing only the parts you want

Every piece of the install is a named component, so you can take just the PreToolUse hook without the skills, CLAUDE.md guidance, or anything else:

```bash
bash setup.sh pretooluse
```

Name any number of components, or use `--without` to take everything except the ones you list:

```bash
bash setup.sh hooks                    # pretooluse + notification + message-display + window-title
bash setup.sh skills guidance          # skills plus the CLAUDE.md guidance block
bash setup.sh --without guidance mcp   # everything except those two
bash setup.sh --list                   # show every component and what it touches
```

| Component         | Installs                                                                       |
| ----------------- | ------------------------------------------------------------------------------ |
| `skills`          | Symlinks skills into `~/.claude/skills/`                                       |
| `pretooluse`      | PreToolUse hook engine + `rules.json`, and the built-in allow/deny permissions |
| `notification`    | macOS attention banners on Notification events                                 |
| `message-display` | MessageDisplay phrase-swap hook                                                |
| `window-title`    | Per-session window titles, the `window-title` CLI, and the status line         |
| `attribution`     | Disables Claude auto-attribution (commit/PR trailers, session URL)             |
| `mcp`             | Registers MCP servers (Playwright)                                             |
| `guidance`        | Upserts the `<agent-skills-guidance>` block in `~/.claude/CLAUDE.md`           |
| `cli`             | `claude-resume` script and the `reclaude` shell alias                          |

### Opting out permanently

Naming components on the command line is a one-off. To keep something off a machine for good, list it under `exclude` in `~/.claude/agent-skills.json`. Every key is a list, and `"all"` in a list excludes everything under that key:

```json
"exclude": {
  "hooks":       ["message-display"],
  "mcp":         ["playwright"],
  "guidance":    ["personal"],
  "skills":      ["author-message", "plan-work", "do-work"],
  "attribution": ["commit"],
  "cli":         ["reclaude"]
}
```

`setup.sh --without <component>` writes the matching entry for you (`--without mcp` becomes `"mcp": ["all"]`, `--without pretooluse` becomes `"hooks": ["pretooluse"]`), so it sticks on every bare run after that. Edit the key to undo. `/setup-agent-skills` asks about exclusions up front so a fresh machine never installs them even once.

On every run `setup.sh` reconciles against the list: it skips installing anything excluded and removes anything excluded that it installed earlier. It only removes what is recognizably its own — a skill symlink that points somewhere else (another clone, an org repo's skill of the same name), an MCP server registered with a different command, or a settings key holding a value we did not write is left alone and mentioned in one line. `shared` cannot be excluded because other skills depend on it, and unknown names are warned about and ignored.

## License

[MIT](LICENSE)
