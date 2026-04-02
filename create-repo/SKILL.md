---
name: create-repo
description: Bootstrap a new monorepo project from a template. Scaffolds the full stack, installs dependencies, verifies everything builds and tests pass, creates a git repo, and optionally pushes to GitHub. Say "create-repo" or "create repo" to start an interactive interview, or pass a template directly like "create-repo fullstack-ts my-app".
argument-hint: "[template] [project-name]"
disable-model-invocation: true
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

After template is resolved, batch the remaining questions in a single `AskUserQuestion` call (up to 4 questions):

**Question 1 — Name:**
- header: `"Name"`
- question: `"What should the project be called? (lowercase-hyphenated, e.g. my-cool-app)"`
- options:
  - label: `"my-app"`, description: `"Default project name"`
  - label: `"my-project"`, description: `"Alternative default"`
- The user will likely choose "Other" and type their own name. That's expected.
- Validate: no spaces, no uppercase, no special chars beyond hyphens.

**Question 2 — Customizations:**
- header: `"Stack"`
- question: `"Any changes to the default stack?"`
- options:
  - label: `"Defaults are fine (Recommended)"`, description: `"Use the standard template as-is"`
  - label: `"Let me specify"`, description: `"I want to swap out or add specific technologies"`
- If they pick "Let me specify", ask a follow-up for details.

**Question 3 — GitHub:**
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
5. Git init + first commit
6. GitHub repo (if opted in)

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
- **Agent 3 — API & RPC:** hono, @hono/trpc-server, @trpc/server, @trpc/client, @trpc/react-query, @tanstack/react-query
- **Agent 4 — Database:** @prisma/client, prisma
- **Agent 5 — Dev tools:** typescript, @biomejs/biome, vitest, playwright, @playwright/test

Each agent should run `npm view <package> version` for each package and return the results. On failure (network error, package not found), the agent should report the error clearly.

After all agents return, merge the results and run **compatibility checks**:
- React version must be compatible with the React types version
- Prisma client and CLI must match
- Tailwind v4 requires compatible PostCSS
- tRPC client and server versions must match

If any incompatibility is detected, resolve it before proceeding (typically by pinning to the last compatible version).

Write the merged results to a `versions.json` file for the scaffold step.

**For Python packages** (fullstack-python, api-python templates): add an agent for Python deps using `uv pip compile` or PyPI checks.

**For Swift** (swift-ts template): check `xcodebuild -version` for the installed Xcode toolchain version.

**Mark task completed.**

---

## Step 5: Scaffold

**Mark task in_progress.**

Create the project directory and all files. Spawn a **scaffold agent** to do the file creation work — this keeps the main context clean from the large volume of file writes.

The agent receives: project name, template name, output directory, versions.json, and any customizations. It creates all files and reports back the directory structure.

The structure varies by template but follows these conventions:

### Common structure (all templates)

```
<project-name>/
├── apps/                    # Application packages
├── packages/                # Shared packages
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions: lint + typecheck + test
├── .gitignore
├── biome.json               # Biome config (strict, noExplicitAny: error)
├── docker-compose.yml       # Local Postgres (+ any other services)
├── pnpm-workspace.yaml
├── turbo.json
├── package.json             # Root package.json with workspace scripts
├── tsconfig.json            # Root TS config (TS templates only)
├── CLAUDE.md                # Root CLAUDE.md for agentic development
├── .claude/
│   └── rules/
│       ├── testing.md
│       ├── modules.md
│       └── types.md
└── README.md                # Project name + how to run
```

### Template: fullstack-ts

```
apps/
├── web/                     # Vite + React + Tailwind + shadcn/ui
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx          # Basic app with tRPC provider
│   │   ├── lib/
│   │   │   └── trpc.ts      # tRPC client setup
│   │   └── components/      # shadcn component directory
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── CLAUDE.md            # App-specific CLAUDE.md
│   └── __tests__/
│       └── App.test.tsx     # Basic render test
└── api/                     # Hono + tRPC adapter
    ├── src/
    │   ├── index.ts         # Hono server entry + tRPC middleware
    │   ├── router.ts        # Root tRPC router
    │   └── trpc.ts          # tRPC context + init
    ├── tsconfig.json
    ├── package.json
    ├── CLAUDE.md            # App-specific CLAUDE.md
    └── __tests__/
        └── router.test.ts   # Basic tRPC procedure test

packages/
├── db/                      # Prisma schema + client
│   ├── prisma/
│   │   ├── schema.prisma    # Basic User model as starter
│   │   └── seed.ts          # Seed a test user
│   ├── src/
│   │   └── index.ts         # Re-export PrismaClient
│   ├── package.json
│   ├── CLAUDE.md
│   └── tsconfig.json
├── types/                   # Shared TypeScript types
│   ├── src/
│   │   └── index.ts
│   ├── package.json
│   └── tsconfig.json
└── config/                  # Shared configs (tsconfig)
    ├── tsconfig.base.json
    └── package.json
```

### Template: fullstack-graphql

Same as fullstack-ts but replace tRPC with:
- `apps/api/` uses Yoga + Pothos instead of tRPC adapter
- `apps/web/` uses Apollo Client + Apollo Provider instead of tRPC client
- `packages/` adds a `graphql/` package with generated types (codegen)
- Include `graphql-codegen` config for type generation from schema

### Template: fullstack-python

```
apps/
├── web/                     # Same as fullstack-ts web (Vite + React + Tailwind)
└── api/                     # FastAPI
    ├── src/
    │   ├── main.py          # FastAPI app entry
    │   ├── routes/
    │   │   └── health.py    # Health check endpoint
    │   └── models/
    │       └── __init__.py
    ├── tests/
    │   └── test_health.py   # Basic endpoint test
    ├── pyproject.toml
    └── Dockerfile

packages/                    # TS shared packages only
├── types/
└── config/
```

Uses `uv` for Python dependency management. `turbo.json` includes Python-aware task definitions.

### Template: api-ts

Same as fullstack-ts but without `apps/web/`. Just `apps/api/` + `packages/db/` + `packages/types/`.

### Template: api-python

Same as fullstack-python but without `apps/web/`. Just `apps/api/` (FastAPI) + minimal packages.

### Template: swift-ts

```
apps/
├── ios/                     # Xcode project (generated via xcodegen or swift package init)
│   ├── Sources/
│   │   ├── App.swift        # @main App entry
│   │   ├── ContentView.swift
│   │   └── API/
│   │       └── Client.swift  # Generated OpenAPI client
│   ├── Tests/
│   │   └── AppTests.swift
│   └── project.yml          # xcodegen spec (if using xcodegen)
│                             # Targets: iOS, iPadOS, Designed for iPad (Mac), visionOS
└── api/                     # Hono + REST + OpenAPI
    ├── src/
    │   ├── index.ts
    │   ├── routes/
    │   │   └── health.ts
    │   └── openapi.ts       # OpenAPI spec generation (e.g., via zod-openapi or hono/zod-openapi)
    ├── tsconfig.json
    ├── package.json
    └── __tests__/
        └── routes.test.ts

packages/
├── db/                      # Prisma + Postgres
└── config/
```

Uses OpenAPI spec generation from the Hono routes, which can be used to auto-generate a typed Swift client.

### Scaffolding rules

- **Every app and package gets a test.** At minimum one passing test that proves the thing starts/renders/responds.
- **Use workspace references** for internal dependencies (e.g., `"@<project>/db": "workspace:*"`).
- **turbo.json** defines: `build`, `dev`, `test`, `lint`, `typecheck` pipelines.
- **Root package.json** scripts: `dev`, `build`, `test`, `lint`, `typecheck`, `db:push`, `db:studio` (where applicable).
- **docker-compose.yml** includes Postgres with a named volume, health check, and a `.env.example` with `DATABASE_URL`.
- **README.md** includes: project name, stack overview, prerequisites (Node, pnpm, Docker), setup commands (`pnpm install`, `docker compose up -d`, `pnpm db:push`, `pnpm dev`), and test command (`pnpm test`).
- **Biome** replaces ESLint + Prettier. Use strict config with `noExplicitAny: error`.
- **CLAUDE.md** files at root and in each app/package. `.claude/rules/` with testing, modules, and types rules.

If the user requested customizations, apply them after the base scaffold — edit the scaffolded files rather than trying to template everything. Report what you changed.

**Mark task completed.**

---

## Step 6: Install & Verify

**Mark task in_progress.**

After creating all files, run verification. Spawn a **verification agent** to handle this — it's long-running and produces verbose output that doesn't need to be in the main context.

The agent runs these steps in sequence:

1. **Install dependencies:**
   ```bash
   cd <project-dir> && pnpm install
   ```
   For Python templates, also run `cd apps/api && uv sync`.

2. **Start services:**
   ```bash
   docker compose up -d
   ```
   Wait for Postgres health check to pass.

3. **Push database schema** (if Prisma):
   ```bash
   pnpm db:push
   ```

4. **Run the full verification suite:**
   ```bash
   pnpm build && pnpm typecheck && pnpm lint && pnpm test
   ```

5. **Verify dev server starts** (briefly — start it, confirm no crashes, check ports, then stop):
   ```bash
   pnpm dev
   ```
   Check that it binds to the expected ports. Stop after confirming.

The agent reports back: pass/fail per step, with error details for any failures.

If any step fails: diagnose and fix. Common issues: port conflicts (try different ports), missing system dependencies (report to user), version incompatibilities (pin to compatible versions). Do not proceed to git until everything passes.

**Mark task completed.**

---

## Step 7: Git Init + First Commit

**Mark task in_progress.**

```bash
git init
git add -A
git commit -m "Initial scaffold: <template> monorepo

Stack: <list key technologies and versions>
Generated by create-repo skill."
```

This first commit is important — it establishes the clean baseline before any application code is written.

**Mark task completed.**

---

## Step 8: GitHub Repo (if opted in)

**Mark task in_progress.**

```bash
gh repo create <project-name> --private --source=. --push
```

This creates the repo on GitHub, sets it as the origin, and pushes the initial commit.

If the user opted out: skip this step and mark completed immediately.

**Mark task completed.**

---

## Step 9: Report & Next Steps

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
