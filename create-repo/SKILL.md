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

---

## Step 1: Interview (skip if both arguments provided)

### Project name

If no project name was provided, ask: "What should the project be called?" Accept lowercase-hyphenated names (e.g., `my-cool-app`). Validate: no spaces, no uppercase, no special chars beyond hyphens.

### Template selection

If no template was provided, present the options:

> "What kind of project?
>
> 1. **fullstack-ts** — React + Hono API + tRPC + Prisma/Postgres + Tailwind/shadcn
> 2. **fullstack-graphql** — React + Hono API + GraphQL (Yoga/Pothos) + Apollo Client + Prisma/Postgres + Tailwind/shadcn
> 3. **fullstack-python** — React + FastAPI + Tailwind/shadcn + Postgres
> 4. **api-ts** — Hono API + tRPC + Prisma/Postgres (no frontend)
> 5. **api-python** — FastAPI + SQLModel/Postgres (no frontend)
> 6. **swift-ts** — Swift iOS/iPadOS/Mac/visionOS app + Hono API + Prisma/Postgres + OpenAPI
>
> Pick a number or name, or describe what you need and I'll recommend one."

If the user describes something that doesn't exactly match a template, recommend the closest one and ask if they want to customize it.

### Customizations

After template selection, ask: "Any changes to the default stack? (e.g., 'use Express instead of Hono', 'add Redis', 'use MySQL instead of Postgres'). Or just say 'defaults are fine'."

Wait for their answer. If they request changes, note them — you'll apply them during scaffolding.

### GitHub repo

Ask: "Create a GitHub repo? (y/n, default: yes)" If yes, it will be created under the user's account as a private repo. They can change visibility later.

---

## Step 2: Resolve Current Versions

Before scaffolding, resolve the latest stable versions of all dependencies in the chosen template. This ensures the project starts on current, compatible versions rather than whatever was hardcoded when this skill was written.

**For npm packages:** Use `npm view <package> version` to get the latest stable version for each key dependency. Do this for all major packages in the template (framework, UI libs, dev tools, etc.).

**For Python packages:** Use `uv pip compile` or check PyPI for latest stable versions.

**For Swift:** Use the latest stable Xcode toolchain. Check `xcodebuild -version` for the installed version.

**Compatibility check:** After resolving versions, verify known compatibility constraints:
- React version must be compatible with the React types version
- Prisma client and CLI must match
- Tailwind v4 requires PostCSS compatibility
- tRPC client and server versions must match

If any incompatibility is detected, resolve it before proceeding (typically by pinning to the last compatible version).

---

## Step 3: Scaffold

Create the project directory and all files. The structure varies by template but follows these conventions:

### Common structure (all templates)

```
<project-name>/
├── apps/                    # Application packages
├── packages/                # Shared packages
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions: lint + typecheck + test
├── .gitignore
├── .prettierrc
├── eslint.config.js         # ESLint flat config
├── docker-compose.yml       # Local Postgres (+ any other services)
├── pnpm-workspace.yaml
├── turbo.json
├── package.json             # Root package.json with workspace scripts
├── tsconfig.json             # Root TS config (TS templates only)
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
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── __tests__/
│       └── App.test.tsx     # Basic render test
└── api/                     # Hono + tRPC adapter
    ├── src/
    │   ├── index.ts         # Hono server entry + tRPC middleware
    │   ├── router.ts        # Root tRPC router
    │   └── trpc.ts          # tRPC context + init
    ├── tsconfig.json
    ├── package.json
    └── __tests__/
        └── router.test.ts   # Basic tRPC procedure test

packages/
├── db/                      # Prisma schema + client
│   ├── prisma/
│   │   └── schema.prisma    # Basic User model as starter
│   ├── src/
│   │   └── index.ts         # Re-export PrismaClient
│   ├── package.json
│   └── tsconfig.json
├── types/                   # Shared TypeScript types
│   ├── src/
│   │   └── index.ts
│   ├── package.json
│   └── tsconfig.json
└── config/                  # Shared configs (tsconfig, eslint)
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

---

## Step 4: Install & Verify

After creating all files:

1. **Install dependencies:**
   ```bash
   cd <project-name> && pnpm install
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

5. **Verify dev server starts** (briefly — start it, confirm no crashes, then stop):
   ```bash
   pnpm dev
   ```
   Check that it binds to the expected ports. Stop after confirming.

If any step fails: diagnose and fix. Common issues: port conflicts (try different ports), missing system dependencies (report to user), version incompatibilities (pin to compatible versions). Do not proceed to git until everything passes.

---

## Step 5: Git Init + First Commit

```bash
git init
git add -A
git commit -m "Initial scaffold: <template> monorepo

Stack: <list key technologies and versions>
Generated by create-repo skill."
```

This first commit is important — it establishes the clean baseline before any application code is written. Take-home evaluators and collaborators look at commit history.

---

## Step 6: GitHub Repo (if opted in)

```bash
gh repo create <project-name> --private --source=. --push
```

This creates the repo on GitHub, sets it as the origin, and pushes the initial commit.

If the user opted out: skip this step. They can always run `gh repo create` later.

Report: "Project created at `./<project-name>/`. GitHub repo: `https://github.com/<user>/<project-name>`" (or "local only" if no GitHub).

---

## Step 7: Next Steps

Suggest what to do next based on the template:

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
