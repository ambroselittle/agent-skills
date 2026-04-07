---
name: create-repo
description: Bootstrap a new monorepo project from a template. Scaffolds the full stack, installs dependencies, verifies everything builds and tests pass, creates a git repo, and optionally pushes to GitHub. Say "create-repo" or "create repo" to start an interactive interview, or pass a template directly like "create-repo fullstack-ts my-app".
argument-hint: "[template] [project-name]"
---

# Create Repo: Bootstrap a New Project

You are a project scaffolding assistant. Your job is to create a well-structured monorepo from a template, verify it works, and get it into version control with a clean first commit.

**Arguments:** $ARGUMENTS
- `$ARGUMENTS[0]` — template name (optional, will prompt if missing)
- `$ARGUMENTS[1]` — project name (optional, will prompt if missing)

## CRITICAL: Do Not Install Global Dependencies

**NEVER install, upgrade, or modify globally-installed tools** (e.g., `npm install -g`, `corepack enable`, `corepack install`, `brew install`, `pip install`, etc.) without explicit user approval. This includes package managers, runtimes, CLI tools, and anything that modifies the system outside the project directory.

If a required tool is missing or outdated:
1. Run the preflight check (Step 3)
2. Show the user what's missing
3. Offer the generated `install-deps.sh` script
4. **STOP and WAIT** for the user to install it themselves

This is a hard stop — do not proceed, do not attempt to install it yourself, do not try an alternative tool. The user's machine is their own.

---

## Step 1: Interview (skip answered questions if arguments provided)

Use the `AskUserQuestion` tool for every choice. This gives the user a proper selection UI with defaults they can accept by pressing Enter.

**AskUserQuestion constraints** — the tool requires:
- `questions`: array of 1-4 question objects
- Each question: `question` (string), `header` (max 12 chars), `options` (2-4 items), `multiSelect` (boolean)
- Each option: `label` (1-5 words), `description` (explains the choice)
- The tool auto-adds an "Other" option for free-text input — don't add one yourself
- Put the recommended/default option first in the list and add "(Recommended)" to its label

You can batch up to 4 independent questions in a single `AskUserQuestion` call. Use this to ask multiple things at once when they don't depend on each other.

### Template selection (two questions if needed)

If both template arguments are provided (e.g., `create-repo fullstack-ts my-app`), skip the interview entirely.

If no template was provided, first ask the **category**:

**Question 1 — Category:**
- header: `"Stack"`
- question: `"What kind of project?"`
- options:
  - label: `"Fullstack (Recommended)"`, description: `"Frontend + API + database — web or mobile app with a backend"`
  - label: `"API only"`, description: `"Backend API + database, no frontend"`
  - label: `"Mobile + API"`, description: `"Swift iOS/iPadOS/Mac/visionOS app with a TypeScript API"`

Then based on the category, ask the **variant** (skip if the category only has one option):

**If Fullstack:**
- header: `"Variant"`
- question: `"Which fullstack flavor?"`
- options:
  - label: `"TypeScript + tRPC (Recommended)"`, description: `"React + Hono + tRPC + Prisma/Postgres + Tailwind/shadcn"`
  - label: `"TypeScript + GraphQL"`, description: `"React + Hono + Yoga/Pothos + Apollo Client + Prisma/Postgres + Tailwind/shadcn"`
  - label: `"Python API"`, description: `"React frontend + FastAPI backend + Postgres + Tailwind/shadcn"`
- Maps to: `fullstack-ts`, `fullstack-graphql`, `fullstack-python`

**If API only:**
- header: `"Variant"`
- question: `"TypeScript or Python?"`
- options:
  - label: `"TypeScript (Recommended)"`, description: `"Hono + tRPC + Prisma/Postgres"`
  - label: `"Python"`, description: `"FastAPI + SQLModel/Postgres"`
- Maps to: `api-ts`, `api-python`

**If Mobile + API:** No variant question needed — maps directly to `swift-ts`.

### Project name, output directory, customizations, and GitHub

After template is resolved, ask the project description first (needed to generate name suggestions), then batch the remaining questions:

**Round 1 — single question:**

**Question 1 — What it does:**
- header: `"About"`
- question: `"What will this project do? (one sentence — helps generate a good name, or skip for a random one)"`
- options:
  - label: `"Skip"`, description: `"Just give me a creative name"`

**Round 2 — batch the rest (up to 4 questions):**

**Question 2 — Name:**

Generate 3–4 name suggestions as the options. Names should be lowercase-hyphenated, memorable, and short (1–2 words).

**Channel your inner naming consultant.** The best project names are like the best band names — they stick, they spark curiosity, and they sound good when you say them out loud. Draw from mythology, science, obscure words, culinary terms, nautical language, music, architecture, nature — whatever resonates with the project's soul. Puns and wordplay welcome. Boring is the only wrong answer.

- **If the user described the project:** generate names that rhyme with the domain — not literally but emotionally. A recipe app could be `mise`, `saffron`, `mortar`; a task tracker could be `cadence`, `slate`, `trellis`; a chat app could be `murmur`, `signal-fire`, `parlor`. Never suggest literal descriptions (`recipe-app`, `task-tracker`) — that's what boring tools do.
- **If the user skipped:** go wild. Generate names with personality — the kind that make you want to build something just because the name is that good. `zephyr`, `anvil`, `foxglove`, `parallax`. Vary the vibe: one playful, one elegant, one punchy, one weird.

Present as options:
- header: `"Name"`
- question: `"Pick a name or type your own (lowercase-hyphenated)"`
- options: your 3–4 generated names, each with a one-line description explaining the inspiration (e.g., `label: "saffron"`, `description: "A rare spice — for a project with flavor"`)
- The user can always pick "Other" and type their own. That's expected and fine.
- Validate: no spaces, no uppercase, no special chars beyond hyphens.

**Question 3 — Output directory:**
- header: `"Location"`
- question: `"Where should the project be created?"`
- options:
  - label: `"./<project-name> (Recommended)"`, description: `"Create in a subdirectory of the current working directory"`
  - label: `"~/Code/<project-name>"`, description: `"Create in your Code directory"`
- The user will likely choose "Other" and type their own path. That's expected.
- Resolve `~` and relative paths. The scaffold `--output` flag receives this value.

**Question 4 — Customizations:**
- header: `"Stack"`
- question: `"Any changes to the default stack?"`
- options:
  - label: `"Defaults are fine (Recommended)"`, description: `"Use the standard template as-is"`
  - label: `"Let me specify"`, description: `"I want to swap out or add specific technologies"`
- If they pick "Let me specify", ask a follow-up for details.

**Question 5 — GitHub:**
- header: `"GitHub"`
- question: `"Create a private GitHub repo and push?"`
- options:
  - label: `"Yes (Recommended)"`, description: `"Create a private repo under your account and push the initial commit"`
  - label: `"No"`, description: `"Local only — you can push later with gh repo create"`

---

## Step 2: Set Up Progress Tracking

Create a task list using the `TaskCreate` tool to track progress through the remaining steps. This gives the user visibility into where you are and what's left. Create one task per step:

1. Preflight check
2. Resolve versions
3. Scaffold project
4. Install & verify
5. Git init + GitHub

Mark each task `in_progress` when starting it and `completed` when done.

---

## Step 3: Preflight Check (BLOCKING — nothing proceeds until this passes)

**Mark task in_progress.**

This step is a hard gate. No version resolution, no scaffolding, no file creation of any kind until preflight passes clean.

Run the preflight environment checker:
```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.preflight --template <template>
```

**If it exits 0:** All tools are present and at required versions. Mark task completed and continue.

**If it exits non-zero:** 
1. Show the user the full preflight output (the table of what's missing/outdated)
2. Tell them a script has been generated to install everything:
   ```
   bash install-deps.sh
   ```
3. **STOP COMPLETELY.** Use `AskUserQuestion` to ask: "Some required tools are missing. Run `bash install-deps.sh` to install them, then let me know when you're ready to continue."
4. When the user confirms, re-run preflight to verify. If it still fails, repeat this cycle.
5. Do NOT attempt to install anything yourself. Do NOT skip ahead. Do NOT try to work around missing tools.

**Mark task completed** only after preflight exits 0.



---

## Step 4: Resolve Current Versions

**Mark task in_progress.**

Before scaffolding, resolve the latest stable versions of all dependencies in the chosen template. This ensures the project starts on current, compatible versions rather than whatever was hardcoded when this skill was written.

**Spawn parallel sub-agents** to resolve versions concurrently. Each agent handles one category and reports back a JSON object of `{ "package": "version" }` pairs. This keeps the main context clean and runs lookups in parallel:

- **Agent 1 — Frontend core:** react, react-dom, @types/react, @types/react-dom, vite, @vitejs/plugin-react
- **Agent 2 — Styling:** tailwindcss, @tailwindcss/vite
- **Agent 3 — API & RPC:** hono, @hono/node-server, @hono/trpc-server, @trpc/server, @trpc/client, @trpc/react-query, @tanstack/react-query
- **Agent 4 — Database:** @prisma/client, prisma, @prisma/adapter-pg, dotenv
- **Agent 5 — Dev tools:** typescript, @biomejs/biome, vitest, playwright, @playwright/test

Each agent should run `npm view <package> version` for each package and return the results. On failure (network error, package not found), the agent should report the error clearly.

After all agents return, merge the results and run **compatibility checks**:
- React version must be compatible with the React types version
- Prisma client and CLI must match
- Tailwind v4 requires compatible PostCSS
- tRPC client and server versions must match

If any incompatibility is detected, resolve it before proceeding (typically by pinning to the last compatible version).

Write the merged results to a `versions.json` file for the scaffold step.

**Version caching:** After resolving, save the versions to `~/.agent-skills/.version-cache/<template>.json` using the format:
```json
{
  "cached_at": <unix-timestamp>,
  "cached_at_human": "<ISO-8601>",
  "template": "<template>",
  "versions": { ... }
}
```

Before spawning agents, check if a cache file exists and is less than 24 hours old. If so, skip resolution and use the cached versions — just inform the user: "Using cached versions from [time]. Pass `--fresh` or say 'resolve fresh versions' to re-check."

**For Python packages** (fullstack-python, api-python templates): add an agent for Python deps using `uv pip compile` or PyPI checks.

**For Swift** (swift-ts template): check `xcodebuild -version` for the installed Xcode toolchain version.

**Mark task completed.**

---

## Step 5: Scaffold

**Mark task in_progress.**

Run the scaffold script to create all project files from Jinja2 templates:

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.scaffold \
  --project-name <name> \
  --template <template> \
  --versions <path-to-versions.json> \
  --output <output-dir>
```

The script renders `templates/common/` (shared across all templates) and `templates/<template>/` (template-specific files), substituting project name, scope, and dependency versions.

**If the user requested customizations:** After the scaffold script completes, apply customizations by editing the scaffolded files directly. This is where the model adds value — interpreting "use Express instead of Hono" and making the right changes across package.json, server entry point, etc. Report what you changed.

**Mark task completed.**

---

## Step 5b: Setup Environment

After scaffolding and before verification, run the setup script to initialize ports and environment:

```bash
cd <output-dir> && pnpm project:setup
```

This discovers free ports, writes `.env.ports`, generates root `.env` and per-package `.env` files, and sets `COMPOSE_PROJECT_NAME` for Docker isolation. This makes verification deterministic — no missing `.env` failures.

---

## Step 6: Install & Verify

**Mark task in_progress.**

Run the verification script:

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.verify <output-dir>
```

This runs the full pipeline in sequence: `pnpm install` → `prisma generate` → `biome format` → `docker compose up` → `db push` → `build` → `typecheck` → `lint` → `test` → dev server smoke check → E2E tests. It reports per-step pass/fail with timing.

**If verification passes:** Mark task completed and continue.

**If verification fails:** The script reports which step failed and the error output. Diagnose and fix the issue, then re-run. If the failure is caused by a breaking change in a dependency (e.g., major version upgrade of Prisma, Biome, etc.), track the fix — it becomes a template improvement candidate for the Step 9 report. Common fixes:
- Port conflict → change the port in the config or re-run `pnpm project:setup`
- Missing `.env` → run `pnpm project:setup` to generate from `.env.example`
- Type errors → fix the generated code
- Test failures → fix the test or the code it tests

Do not proceed to git until verification passes cleanly.

**Mark task completed.**

---

## Step 7: Git Init + First Commit + GitHub

**Mark task in_progress.**

Run the git initialization script:

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.init_git <output-dir> \
  --project-name <name> \
  --template <template> \
  --stack "<stack description, e.g. React 19 + Hono + tRPC + Prisma + Tailwind v4>"
```

Add `--no-github` if the user opted out of GitHub repo creation.

The script handles: `git init`, staging, initial commit with stack description, and (optionally) `gh repo create --private --source=. --push`.

**Mark task completed.**

---

## Step 8: Report & Next Steps

Mark all tasks completed.

Report results, then suggest what to do next:

> "Your `<project-name>` is ready. Everything builds, tests pass, and the first commit is pushed.
>
> To start developing:
> ```bash
> cd <project-name>
> docker compose up -d   # if not already running
> pnpm dev
> ```
>
> Next steps:
> - Run `/start-work` to plan your first feature
> - The starter includes a basic health check — start building from there
> - Tests run with `pnpm test` (Vitest/pytest depending on template)"

---

## Step 9: Template Improvement Report

If any fixes were needed during verification (Step 6) — e.g., a dependency version introduced a breaking change that the templates don't account for — write a summary of template changes needed to `.work/create-repo-template-fixes/plan.md` in the agent-skills repo. Include:
- What broke and why (dependency version change, config format change, etc.)
- Exact file changes needed in the templates
- Whether the fix should be deterministic (template/script change) or kept as AI-handled

This ensures template improvements are tracked and can be applied by a follow-up agent.

---

## Guidelines

- **Verify before committing.** The first commit must be a working project — build passes, tests pass, dev server starts. No broken scaffolds.
- **Use current versions.** Always resolve latest stable versions at creation time. Never hardcode versions in this skill.
- **Respect customizations.** If the user asked for Express instead of Hono, give them Express instead of Hono. The templates are defaults, not mandates.
- **Keep it minimal.** The scaffold should have just enough to prove each layer works (one model, one route, one component, one test each). It's a starting point, not a finished app.
- **Don't add auth, state management, or other cross-cutting concerns.** Those come later, driven by the specific app's needs.
- **Test files are not optional.** Every app and package gets at least one test. This is non-negotiable — it proves the testing pipeline works and sets the expectation for the project.
- **Use sub-agents for heavy work.** Version resolution, scaffolding, and verification should all run in agents to keep the main conversation context clean and responsive.
- **Track progress with tasks.** The user should always be able to see where you are in the process.
- **Never install global tools.** If something is missing, the preflight check catches it. Show the user the install script and let them run it. Their machine, their choice.
