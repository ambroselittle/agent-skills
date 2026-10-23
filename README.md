# Agent Skills 🤖✨

**Make your agents awesomer.** Shared skills, policy hooks, and guidance for Claude Code and Codex, with small integrations for their different tool APIs.

Clone or fork this repo and run `make init` — you immediately get all three.

```bash
git clone https://github.com/ambroselittle/agent-skills
cd agent-skills
make init
```

## Claude and Codex installation

`setup.sh` detects installed Claude Code and Codex agents and configures each supported integration. Reapplying setup refreshes their managed guidance together. Use `--target claude|codex|both` to override detection explicitly.

Preview setup without changing installed files:

```bash
bash setup.sh --dry-run
```

Install only Codex policy hooks:

```bash
bash setup.sh --target codex pretooluse
```

`--list` shows components; selection and persistent `--without` exclusions work for detected or explicitly selected agents. `CODEX_HOME` is respected. `AGENT_SKILLS_USER` selects a personal guidance template; otherwise setup uses the cached user or your GitHub login.

| Component | Claude | Codex |
| --- | --- | --- |
| Policy engine | Existing allow/deny/ask behavior | Explicit denials; other decisions defer to native approvals |
| Guidance | Managed CLAUDE.md block | Managed AGENTS.md block |
| Skills | Links in `~/.claude/skills` | Links in `~/.agents/skills` |
| Titles | Terminal title + topical reminders | Native `/title` and `/rename` |
| Display swaps, notifications, attribution, MCP, resume CLI | Existing integrations | Native Codex configuration |

One source of guidance is maintained in `templates/user-common.md` plus a personal `templates/<username>.md` overlay. `user-claude.md` and `user-codex.md` contain only integration details. Setup refreshes their managed blocks while preserving all other text. Repo `AGENTS.md` links to `CLAUDE.md`; portable skills likewise use one maintained source. `supportedAgents` arrays in `skills/compatibility.json` record compatibility. Existing directories and links owned by other installers are preserved.

### Shared runtime and configuration

Both agents read `~/.agent-skills/config.json`. Shared preferences such as `work_root`, `user_prefix`, and exclusions live at the top level; per-agent differences live under `agents.claude` or `agents.codex`. Setup automatically applies versioned migrations, imports legacy Claude preferences and Codex overrides, retains the original files, and preserves unrelated hooks and configuration.

Resources are available through `~/.agent-skills/skills/<name>`, commands through `~/.agent-skills/scripts/<name>/<script>`, and the selected source checkout through `~/.agent-skills/source`. Scripts use the selected Python 3.12+ runtime at `~/.agent-skills/scripts/python`. The Python-based scaffolder keeps its package, environment, and templates together through its resource directory.

Skills load context explicitly and use the active agent’s question, progress, skill invocation, and delegation capabilities. Generic Low, Medium, and High tiers map to available models in [harness capabilities](skills/shared/references/harness-capabilities.md). Missing optional capabilities have explicit fallbacks; Claude-specific adapters such as transcript reading remain conditional.

### Activate and diagnose Codex hooks

Review new or changed definitions in Codex **`/hooks`**. The installer never
edits trust records. If an already-running session still prompts or runs a
removed hook, exit and resume it; a successful command alone does not establish
that the hook ran.

The policy log at `~/.codex/hooks/agent-skills-policy/codex-events.jsonl` records
session IDs, event/tool names, input shape and decisions, **not commands or file
contents**. A live test must produce an entry for the expected session. Logs
rotate after about 1 MB. The adapter covers shell commands, patch operations, and MCP inputs.

The same rules and private `~/.agent-skills/local-rules.json` overlay are used
by both tools. Codex normalizes patch additions, updates, moves and deletions for
the engine. Unknown inputs and `allow`, `ask`, and `proceed` decisions defer to native Codex handling.
An `ask` rule cannot force a Codex prompt; the adapter only enforces explicit denials. Hooks are not a complete sandbox: hosted tools and some specialized
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

### 📋 Shared Guidance — A Better Collaborator Across Every Project

Installed to `~/.claude/CLAUDE.md` and `${CODEX_HOME:-~/.codex}/AGENTS.md` for detected agents, the shared managed guidance shapes collaboration across projects:

- **Bias toward action** — evaluates actual risk instead of reflexively balking at large changes, which it's prone to from human-limited training data
- **Scope philosophy** — don't shy away from expanding scope when discovered during planning and implementation
- **Blameless improvement culture** — treats errors as system improvement opportunities, not blame occasions (avoid Claude self-flagellation)
- **Batch commits, push once** — avoids burning CI on intermediate states
- **Verify before done** — linting, typechecking, and tests must all pass before reporting complete

**Per-user rules:** The template system supports a `<username>.md` overlay that gets appended automatically when your GitHub username matches. Fork this repo and add `templates/<your-username>.md` to layer in personal preferences on top of the shared core.

---

### ⚡ Skills — Workflow Automation for the Whole Dev Cycle

Skills are agentic superpowers that orchestrate multi-step workflows. Invoke them with `/skill-name` in Claude Code or `$skill-name` in Codex; use the active harness’s installed skill workflow.

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
hooks/           # PreToolUse hook engine, rules.json, and tests
templates/       # Shared + agent integration guidance and personal overlays
setup.sh         # Detects agents, migrates config, links skills and updates guidance
```

## Setup

`make init` ensures `uv`is installed, syncs Python environments, and runs `setup.sh`:

```bash
make init
```

This detects installed agents, migrates shared configuration, links portable skills and commands, installs the applicable integrations, and refreshes each agent’s managed guidance. Claude’s existing hook and permission behavior stays intact; Codex receives the deny-only adapter and uses native approvals.
Idempotent — safe to re-run. In a worktree for this repo, only skills with changes on the branch are relinked, so you can test them prior to merging more easily.

### Installing only the parts you want

Every piece of the install is a named component, so you can take just the PreToolUse hook without the skills, managed guidance, or anything else:

```bash
bash setup.sh pretooluse
```

Name any number of components, or use `--without` to take everything except the ones you list:

```bash
bash setup.sh hooks                    # pretooluse + notification + message-display + window-title
bash setup.sh skills guidance          # skills plus installed agents’ guidance
bash setup.sh --without guidance mcp   # everything except those two
bash setup.sh --list                   # show every component and what it touches
```

| Component | Installs |
| --- | --- |
| `skills` | Symlinks compatible skills into the detected agents’ skill directories |
| `pretooluse` | PreToolUse hook engine + `rules.json`, and the built-in allow/deny permissions |
| `notification` | macOS attention banners on Notification events |
| `message-display` | MessageDisplay phrase-swap hook |
| `window-title` | Per-session window titles, the `window-title` CLI, and the status line |
| `attribution` | Disables Claude auto-attribution (commit/PR trailers, session URL) |
| `mcp` | Registers MCP servers (Playwright) |
| `guidance` | Refreshes installed agents’ `<agent-skills-guidance>` blocks |
| `cli` | `claude-resume` script and the `reclaude` shell alias |

### Opting out permanently

Naming components on the command line is a one-off. To keep something off a machine for good, list it under `exclude` in `~/.agent-skills/config.json`. Every key is a list, and `"all"` in a list excludes everything under that key:

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
