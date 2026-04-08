# Agent Skills 🤖✨

**Make Claude awesomer.** A collection of skills, hooks, and CLAUDE.md guidance that turn Claude Code into a sharper, safer, more opinionated engineering collaborator.

Clone or fork this repo and run `make init` — you immediately get all three.

```bash
git clone https://github.com/ambroselittle/agent-skills
cd agent-skills
make init
```

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
/start-work → /plan-review → /hack → /ship → /code-review → /apply-review-fixes → /learn
```

| Skill | What it does |
| --- | --- |
| `/start-work` | Takes a GitHub issue or description, discovers relevant code, and produces a phased implementation plan in `.work/<slug>/plan.md`; unlike Claude's built in plans, these survive sessions and can be saved historically |
| `/plan-review` | Runs parallel specialized agents (architecture, completeness, security, testing) over the plan before a line of code is written. Planning is 10x more important with agentic dev, and getting it right saves time, rework, and cost. |
| `/hack` | Implements work from a plan phase by phase — coordinates sub-agents, verifies, commits per task. Supports full auto mode — fire and forget until it's ready for review. |
| `/ship` | Verifies, commits, pushes, and opens a PR. Runs a docs sanity check and fills the repo's PR template. |
| `/code-review` | Multi-pass parallel review with specialized agents. Two-pass approach (normal + reversed diff) for higher recall. Presents findings without touching code. |
| `/apply-review-fixes` | Takes the findings from `/code-review`, applies fixes, verifies, and commits. Separated so you can review findings before anything changes. |
| `/learn` | Routes lessons from a work item to skill updates, repo-local rules, or user CLAUDE.md guidance — closing the improvement loop. |
| `/fix-tests` | Diagnoses CI test failures, groups by root cause, and fixes methodically. |
| `/make-skill` | Interactive interview to create a new skill from scratch. |

---

### 🏗️ `/create-repo` — AI-Assisted Project Starter Kit

Bootstrap a realistic monorepo in minutes. The skill interviews you about your project, resolves current package versions, scaffolds the full stack, verifies it builds and passes lint/tests, and makes the first commit.

**Supported templates:**

| Template | Stack |
| --- | --- |
| `fullstack-ts` | React + Tailwind + shadcn/ui · Hono API · tRPC · Prisma + PostgreSQL · Turborepo · Vitest · Biome |
| `fullstack-graphql` | React + Tailwind + shadcn/ui · Hono API · GraphQL (Yoga + Pothos) · Prisma + PostgreSQL · Turborepo · Vitest · Biome |
| `fullstack-python` | React + Tailwind + shadcn/ui · FastAPI · SQLModel + Alembic · PostgreSQL · Ruff · pytest |
| `api-ts` | Hono REST API · Prisma + PostgreSQL · Vitest · Biome |
| `api-python` | FastAPI · SQLModel + Alembic · PostgreSQL · Ruff · pytest |
| `swift-ts` | Swift multiplatform app (iOS/iPadOS/visionOS) · Hono REST API · OpenAPI typed client · Prisma + PostgreSQL |

Every scaffold includes: dynamic port discovery (no hardcoded ports), docker-compose for local dev, a task runner, test scaffolding, and a clean lint baseline.

---

## Repo Structure

```
skills/          # Skill definitions (SKILL.md + agents, scripts, references)
hooks/           # PreToolUse hook engine, rules.json, and tests (~415 tests)
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

## License

[MIT](LICENSE)