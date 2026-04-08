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

**NEVER install, upgrade, or modify globally-installed tools** (e.g., `npm install -g`, `brew install`, `pip install`, etc.) without explicit user approval. This includes package managers, runtimes, CLI tools, and anything that modifies the system outside the project directory.

If a required tool is missing or outdated:
1. Run the preflight check (Step 3)
2. Show the user what's missing
3. Offer the generated `install-deps.sh` script
4. **STOP and WAIT** for the user to install it themselves

This is a hard stop — do not proceed, do not attempt to install it yourself, do not try an alternative tool. The user's machine is their own.

---

## Step 1: Interview (skip answered questions if arguments provided)

The repo home finder results are pre-loaded below. Use them for the Location question.

- Repo home: !`~/.claude/skills/create-repo/scripts/context.sh repo-home`
- Available templates: !`~/.claude/skills/create-repo/scripts/context.sh list-templates`

If the result is empty or `{}`, fall back to `./<project-name>` and `~/Code/<project-name>` as location options.

Use the `AskUserQuestion` tool for every choice. This gives the user a proper selection UI with defaults they can accept by pressing Enter.

**AskUserQuestion constraints** — the tool requires:
- `questions`: array of 1-4 question objects
- Each question: `question` (string), `header` (max 12 chars), `options` (2-4 items), `multiSelect` (boolean)
- Each option: `label` (1-5 words), `description` (explains the choice)
- The tool auto-adds an "Other" option for free-text input — don't add one yourself
- Put the most common/default option first in the list (it becomes the default when the user presses Enter)

You can batch up to 4 independent questions in a single `AskUserQuestion` call. Use this to ask multiple things at once when they don't depend on each other.

### Template selection (two questions if needed)

If both template arguments are provided (e.g., `create-repo fullstack-ts my-app`), skip the interview entirely.

If no template was provided, first ask the **category**:

**Question 1 — Category:**
- header: `"Stack"`
- question: `"What kind of project?"`
- options:
  - label: `"Fullstack"`, description: `"Frontend + API + database — web or mobile app with a backend"`
  - label: `"API only"`, description: `"Backend API + database, no frontend"`
  - label: `"Mobile + API"`, description: `"Swift iOS/iPadOS/Mac/visionOS app with a TypeScript API"`

Then based on the category, ask the **variant** (skip if the category only has one option):

**If Fullstack:**
- header: `"Variant"`
- question: `"Which fullstack flavor?"`
- options:
  - label: `"TypeScript + tRPC"`, description: `"React + Hono + tRPC + Prisma/Postgres + Tailwind/shadcn"`
  - label: `"TypeScript + GraphQL"`, description: `"React + Hono + Yoga/Pothos + Apollo Client + Prisma/Postgres + Tailwind/shadcn"`
  - label: `"Python API"`, description: `"React frontend + FastAPI backend + Postgres + Tailwind/shadcn"`
- Maps to: `fullstack-ts`, `fullstack-graphql`, `fullstack-python`

**If API only:**
- header: `"Variant"`
- question: `"TypeScript or Python?"`
- options:
  - label: `"TypeScript"`, description: `"Hono + tRPC + Prisma/Postgres"`
  - label: `"Python"`, description: `"FastAPI + SQLModel/Postgres"`
- Maps to: `api-ts`, `api-python`

**If Mobile + API:**
- header: `"Confirm"`
- question: `"The mobile template is Swift + TypeScript API (Hono/Prisma/Postgres). Sound good?"`
- options:
  - label: `"Yes, let's go"`, description: `"Swift iOS/iPadOS/Mac/visionOS + Hono REST API + Prisma/Postgres"`
  - label: `"No, go back"`, description: `"Pick a different category"`
- If "Yes" → maps to `swift-ts`. If "No" or "Other" → re-ask the category question.

### Project name, output directory, customizations, and GitHub

After template is resolved, ask the project description first (needed to generate name suggestions), then batch the remaining questions:

**Round 1 — free text (no AskUserQuestion):**

Just ask conversationally: **"What's this project about? (one sentence, or say 'skip' to move on)"**

Read their response as plain text. If they skip, or give a generic/vague answer (e.g., "just testing", "playing around", "trying out the stack", "prototype"), treat it the same as no description — go the creative name route, not literal.

**Round 2 — Name (MUST be a separate AskUserQuestion call — do NOT batch with other questions):**

The name question must be its own `AskUserQuestion` call so you can evaluate the response and potentially loop. If you batch it with Location/Customizations/GitHub, you lose the ability to re-generate names.

Generate 3 name suggestions. Names should be lowercase-hyphenated, memorable, and short (1–2 words).

**Channel your inner naming consultant.** The best project names are like the best band names — they stick, they spark curiosity, and they sound good when you say them out loud. Draw from mythology, science, obscure words, culinary terms, nautical language, music, architecture, nature — whatever resonates with the project's soul. Puns and wordplay welcome. Boring is the only wrong answer.

- **If the user described the project:** generate names that rhyme with the domain — not literally but emotionally. Evoke the feeling, not the function. Never suggest literal descriptions (`recipe-app`, `task-tracker`) — that's what boring tools do.
- **If the user skipped:** go wild. Generate names with personality — the kind that make you want to build something just because the name is that good. Vary the vibe: one playful, one elegant, one punchy, one weird. **NEVER reuse names from these instructions or from prior conversations.** Every set of suggestions must be freshly invented — pull from different domains each time (astronomy, gemstones, cocktails, typography, cartography, martial arts, textiles, philosophy, weather phenomena, musical instruments, architectural elements, etc.).

Present as options:
- header: `"Name"`
- question: `"Let's give it a name. Use \"Type something\" to specify your own or give guidance to generate more options."`
- options: your 3 generated names, each with a one-line description explaining the inspiration (e.g., `label: "saffron"`, `description: "A rare spice — for a project with flavor"`)
- When the user picks "Other" and types something, evaluate what they entered:
  - If it looks like a name (lowercase-hyphenated, no spaces): accept it as the project name.
  - If it looks like guidance (e.g., "something more nautical", "shorter", "try Greek mythology"): generate 3 new names following their direction and re-ask this question.
- Validate final name: no spaces, no uppercase, no special chars beyond hyphens.

**Round 3 — batch the rest (up to 3 questions):**

**Question 3 — Output directory:**
- header: `"Location"`
- question: `"Where should the project be created?"`
- Build options using the **Repo home finder** agent's results. Always include `./<project-name>` as one option. Pick up to 2 more from the cache (deduplicate — if any paths resolve to the same directory, show only one, preferring last_picked > discovered > CWD):
  - `last_picked` (if set): label `"<last_picked>/<project-name>"`, description `"Next to the last one we made"`
  - `discovered` (if set): label `"<discovered>/<project-name>"`, description `"Near other repos we found"`
  - Always: label `"./<project-name>"`, description `"Under current directory"`
  - Fallback (if no last_picked or discovered): label `"~/Code/<project-name>"`, description `"Under Code in home folder"`
- Aim for 2-3 options. The auto-added "Other" lets them type any path.
- Resolve `~` and relative paths. The scaffold `--output` flag receives this value.

**After the user picks a location**, update the cache:
```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.find_repo_home --update-last-picked <parent-dir>
```

**Question 4 — Customizations:**
- header: `"Stack"`
- question: `"Any changes to the default stack?"`
- options:
  - label: `"Defaults are fine"`, description: `"Use the standard template as-is"`
  - label: `"Let me specify"`, description: `"I want to swap out or add specific technologies"`
- If they pick "Let me specify", ask a follow-up for details.

**Question 5 — GitHub:**
- header: `"GitHub"`
- question: `"Create a private GitHub repo and push?"`
- options:
  - label: `"Yes"`, description: `"Create a private repo under your account and push the initial commit"`
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
3. **STOP COMPLETELY.** Use `AskUserQuestion` to confirm:
   - header: `"Preflight"`
   - question: `"Some required tools are missing. Run 'bash install-deps.sh' to install them, then continue."`
   - options:
     - label: `"Done — re-check"`, description: `"I've installed the dependencies, run preflight again"`
     - label: `"Skip for now"`, description: `"I'll handle it manually — continue anyway"`
4. When the user confirms, re-run preflight to verify. If it still fails, repeat this cycle.
5. Do NOT attempt to install anything yourself. Do NOT skip ahead. Do NOT try to work around missing tools.

**Mark task completed** only after preflight exits 0.



---

## Step 4: Resolve Current Versions

**Mark task in_progress.**

Run the version resolution script. It automatically discovers which packages the template needs by scanning `.j2` files, resolves latest stable versions via npm/PyPI, and handles caching (24h TTL):

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.resolve_versions \
  --template <template> \
  --output /tmp/create-repo-versions.json
```

Add `--fresh` if the user asks to re-resolve (e.g., "resolve fresh versions").

If the script fails, it reports which packages couldn't be resolved. Fix by checking network connectivity or adding missing packages to `PACKAGE_REGISTRY` in `scripts/resolve_versions.py`.

**Mark task completed.**

---

## Step 5: Scaffold

**Mark task in_progress.**

Run the scaffold script:

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.scaffold \
  --project-name <name> \
  --template <template> \
  --versions /tmp/create-repo-versions.json \
  --output <output-dir>
```

If the output directory already exists, ask the user if they want to overwrite it. If yes, re-run with `--force` which cleans the directory first. **Never rm -rf the directory yourself.**

The script renders `templates/common/` (shared across all templates) and `templates/<template>/` (template-specific files), substituting project name, scope, and dependency versions.

**If the user requested customizations:** After the scaffold script completes, apply customizations by editing the scaffolded files directly. This is where the model adds value — interpreting "use Express instead of Hono" and making the right changes across package.json, server entry point, etc. Report what you changed.

**Mark task completed.**

---

## Step 5b: Setup Project Environment

After scaffolding and before verification, initialize git (so setup scripts can detect the repo), then run the setup script which installs dependencies, runs port discovery, starts docker/postgres, and pushes database schemas:

```bash
cd <output-dir> && git init -q
```

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.scaffold --setup <output-dir>
```

Add `--skip-docker` if `DATABASE_URL` is already set in the environment (e.g., CI with a service container).

This handles: `pnpm install` / `uv sync` → project setup (port discovery, `.env` generation) → `prisma generate` → `biome format` → `docker compose up` → `db push` → `db seed`. It reports per-step pass/fail with timing.

---

## Step 6: Verify (Quality Checks)

**Mark task in_progress.**

Run the verification script:

```bash
cd ${CLAUDE_SKILL_DIR} && uv run python -m scripts.verify <output-dir>
```

This runs quality checks only (assumes setup is already done): `build` → `typecheck` → `lint` → `test` → dev server smoke check → E2E tests. It reports per-step pass/fail with timing.

**If verification passes:** Mark task completed and continue.

**If verification fails:** The script reports which step failed and the error output. Diagnose and fix the issue, then re-run. If the failure is caused by a breaking change in a dependency (e.g., major version upgrade of Prisma, Biome, etc.), track the fix — it becomes a template improvement candidate for the Step 9 report. Common fixes:
- Port conflict → change the port in the config or re-run `pnpm project:setup`
- Missing `.env` → run `pnpm project:setup` to generate from `.env.example`
- Type errors → fix the generated code
- Test failures → fix the test or the code it tests
- **Version incompatibility** → if the error mentions breaking API changes, deprecated methods, or type mismatches between packages, check `versions.json` for recently bumped major versions. The version resolver grabs latest-of-everything, which can break when a package ships a new major before its ecosystem catches up. Fix by pinning the offending package to the previous major (e.g., `npm view <package> versions` to find the last stable). Check the resolve script's compatibility warnings output for hints.

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

Report results, then give the user a quick-start command. On macOS, pipe it to `pbcopy` so it's ready to paste:

Copy the start command to clipboard (adapts by template):
- TS templates: `echo "cd <output-dir> && pnpm start" | pbcopy`
- Python templates: `echo "cd <output-dir> && just start" | pbcopy`

Then report:

> "Your `<project-name>` is ready. Everything builds, tests pass, and the first commit is pushed.
>
> Quick start copied to clipboard — paste in a terminal to jump in. (Starts Postgres + dev servers in one command.)
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
