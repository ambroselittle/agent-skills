---
skill: start-work
issue: none
branch: ambrose/create-repo-build-out
status: in-progress
---

# Plan: Build out create-repo skill with Python scripts, templates, and eval

> The create-repo skill bootstraps monorepo projects from templates. The current SKILL.md is a placeholder — this plan builds the real implementation: Python-based scaffolding scripts, Jinja2 templates for the fullstack-ts stack, a preflight environment checker, agentic repo scaffolding (CLAUDE.md, rules, PR template), and an eval framework. The skill's SKILL.md becomes a thin AI orchestrator that delegates to deterministic scripts.

## Context

- **Goal:** A working `/create-repo fullstack-ts my-app` that produces a buildable, testable, lintable monorepo with the first commit pushed to GitHub — all driven by Python scripts that the AI orchestrates
- **Scope:** fullstack-ts template only for this work item. Other templates (fullstack-graphql, fullstack-python, api-ts, api-python, swift-ts) will follow in separate work items using the same pattern
- **Stack for fullstack-ts:** Vite 6+ React 19 + Hono + tRPC + Prisma/Postgres + Tailwind v4 + shadcn/ui + Biome + Vitest + Playwright + pnpm + Turborepo
- **Why Python over shell:** Shell scripts start clean and become unmaintainable. Python gives proper error handling, modularity, testability, and subprocess for shell-outs when needed.

## Relevant Files

| File | Role |
|------|------|
| create-repo/SKILL.md | AI orchestrator — needs full rewrite |
| create-repo/scripts/ | Python modules for each phase (new) |
| create-repo/templates/ | Jinja2 template files for each stack (new) |
| create-repo/eval/ | Eval scripts to verify scaffolded repos (new) |
| create-repo/pyproject.toml | Python project config for the scripts (new) |

## Phases

### ~~Phase 1: Project structure and preflight~~ ✓

**Goal:** Establish the Python project structure for create-repo's scripts and build the preflight environment checker. This is the foundation everything else builds on.

**Tasks:**
- [x] `Set up create-repo as a Python project` — Create `create-repo/pyproject.toml` with uv-compatible config. Dependencies: jinja2, pytest (dev). Create `create-repo/scripts/__init__.py`, `create-repo/scripts/preflight.py`, `create-repo/scripts/scaffold.py` (stub), `create-repo/scripts/resolve_versions.py` (stub), `create-repo/scripts/verify.py` (stub), `create-repo/scripts/init_git.py` (stub). Each stub exports its main function with a docstring and `pass` body.
- [x] `Build preflight environment checker` — `scripts/preflight.py` checks for: python 3.12+, node 20+, pnpm 9+, git, gh CLI (+ authenticated check), docker (+ daemon running check), uv (if Python template), xcodegen (if Swift template). Uses `subprocess.run` with `capture_output=True`. Returns a structured result with tool name, required version, found version, status (ok/missing/outdated), and install command. Prints a formatted table to stdout. Exits non-zero if any required tool is missing. Template-specific checks are gated by a `template` argument.
- [x] `Test preflight` — `create-repo/tests/test_preflight.py` with tests: parses version strings correctly, reports missing tools, reports outdated tools, template-specific checks only run for their template. Mock `subprocess.run` to avoid requiring all tools on the test runner.

**Verify (after all tasks in phase):**
- [x] `cd create-repo && uv sync && uv run pytest tests/test_preflight.py -v` passes
- [x] `uv run python -m scripts.preflight --template fullstack-ts` prints the checklist and exits 0 (assuming tools are installed)

---

### ~~Phase 2: Version resolution~~ — DROPPED

> Version resolution stays in the SKILL.md as model-driven parallel agents. Test run proved this works well — the model dynamically discovers current packages and the AskUserQuestion flow handles it. Not worth scripting something that the model handles better and that changes over time.

---

### ~~Phase 3: Scaffold engine + fullstack-ts templates~~ ✓

**Goal:** The core scaffolding script and the fullstack-ts template files. Given a project name and resolved versions, produces a complete directory structure with all files rendered.

**Tasks:**
- [x] `Build Jinja2 template renderer` — `scripts/scaffold.py` takes project_name, template_name, versions_json_path, output_dir. Loads template files from `templates/<template_name>/` and `templates/common/`, renders them with Jinja2 (substituting project name, versions, package names), writes to output_dir preserving directory structure. Template files use `.j2` extension; non-template files (like .gitignore) are copied as-is. The renderer handles nested directories and preserves file permissions (executable bits on scripts).
- [x] `Create common template files` — `templates/common/` contains files shared across all templates: `.gitignore` (Node + Python + macOS + IDE), `biome.json` (strict config, noExplicitAny: error), `.github/workflows/ci.yml.j2` (lint + typecheck + test), `.github/pull_request_template.md`, `docker-compose.yml.j2` (Postgres with health check), `claude-md/root.md.j2` (root CLAUDE.md template), `claude-md/app.md.j2` (per-app CLAUDE.md template), `claude-md/package.md.j2` (per-package CLAUDE.md template), `claude-rules/testing.md`, `claude-rules/modules.md`, `claude-rules/types.md`.
- [x] `Create fullstack-ts template files` — `templates/fullstack-ts/` contains: root `package.json.j2`, `pnpm-workspace.yaml`, `turbo.json`, `tsconfig.json.j2` (strict: true). `apps/web/`: `package.json.j2`, `vite.config.ts.j2` (with API proxy), `tsconfig.json`, `index.html.j2`, `src/main.tsx`, `src/App.tsx.j2` (with tRPC provider), `src/lib/trpc.ts.j2`, `tailwind.config.ts`, `src/app.css` (Tailwind imports), `__tests__/App.test.tsx` (render test), `e2e/smoke.spec.ts.j2` (Playwright: load page, verify API call works), `playwright.config.ts.j2`. `apps/api/`: `package.json.j2`, `tsconfig.json`, `src/index.ts.j2` (Hono server + tRPC adapter + health endpoint), `src/router.ts.j2` (root tRPC router with health + user.list procedures), `src/trpc.ts.j2` (tRPC context with Prisma), `__tests__/router.test.ts.j2` (unit test for tRPC procedures), `__tests__/api.test.ts.j2` (API-level test hitting actual Hono routes). `packages/db/`: `package.json.j2`, `tsconfig.json`, `prisma/schema.prisma.j2` (User model), `prisma/seed.ts.j2` (seed a test user), `src/index.ts` (re-export PrismaClient). `packages/types/`: `package.json.j2`, `tsconfig.json`, `src/index.ts`. `packages/config/`: `package.json.j2`, `tsconfig.base.json`.
- [x] `Test scaffold engine` — Tests that: renders a simple template with variables, preserves directory structure, copies non-template files as-is, handles missing template gracefully, fullstack-ts scaffold produces expected directory structure (check key files exist).

**Verify (after all tasks in phase):**
- [x] `uv run pytest tests/test_scaffold.py -v` passes
- [x] Manual: `uv run python -m scripts.scaffold --project-name test-app --template fullstack-ts --versions versions.json --output /tmp/test-app` produces a directory with the expected structure

---

### ~~Phase 4: Verify and init-git scripts~~ ✓

**Goal:** The verification script (install, build, typecheck, lint, test, dev server smoke) and the git initialization script.

**Tasks:**
- [x] `Build verification script` — `scripts/verify.py` takes a project directory path. Runs in sequence: `pnpm install`, `docker compose up -d` + wait for health, `pnpm db:push`, `pnpm build`, `pnpm typecheck`, `pnpm lint`, `pnpm test`. Then starts `pnpm dev` in background, waits for ports (API + web), does HTTP health check, kills dev servers. Reports each step as pass/fail with timing. Exits non-zero on first failure with clear error message. For the dev server check: parse expected ports from the template config rather than hardcoding.
- [x] `Build git init script` — `scripts/init_git.py` takes project directory, project name, template name, stack description (for commit message), and optional `--no-github` flag. Runs: `git init`, `git add -A`, `git commit` with a formatted initial commit message listing the stack and versions. If GitHub opted in: `gh repo create <name> --private --source=. --push`. Reports the GitHub URL on success. Handles: repo already exists (error with clear message), gh not authenticated (error with auth command).
- [x] `Test verify and init-git` — Unit tests with mocked subprocess calls verifying: correct command sequences, failure handling (what happens when `pnpm build` fails), port detection logic, git commit message format, gh repo create argument construction.

**Verify (after all tasks in phase):**
- [x] `uv run pytest tests/ -v` — all tests pass (47 passing)
- [ ] Integration: scaffold a fullstack-ts project to /tmp, run verify.py against it, confirm all checks pass

---

### ~~Phase 5: Rewrite SKILL.md as orchestrator~~ ✓

**Goal:** The SKILL.md becomes a thin coordinator that runs the interview, then delegates to the Python scripts in sequence.

**Tasks:**
- [x] `Rewrite create-repo SKILL.md` — The new SKILL.md: (1) runs the interview (template, project name, customizations, GitHub opt-in), (2) calls `scripts/preflight.py --template <template>` and stops if it fails, (3) calls `scripts/resolve_versions.py --template <template> --output versions.json`, (4) calls `scripts/scaffold.py --project-name <name> --template <template> --versions versions.json --output ./<name>`, (5) if the user requested customizations, the AI applies them by editing the scaffolded files, (6) calls `scripts/verify.py ./<name>`, (7) calls `scripts/init_git.py ./<name> --template <template>` (with `--no-github` if opted out), (8) reports results and suggests next steps. The skill references scripts via `${CLAUDE_SKILL_DIR}/scripts/`. Include the template descriptions and interview flow from the current SKILL.md.
- [x] `Update CLAUDE.md for create-repo` — Add a CLAUDE.md inside create-repo/ explaining the skill's own structure: scripts/, templates/, eval/, how to add a new template, how to run tests.

**Verify (after all tasks in phase):**
- [ ] The SKILL.md is well-structured and references all scripts correctly
- [ ] The create-repo/CLAUDE.md accurately describes the project

---

### Phase 6: Eval framework

**Goal:** An eval that runs `/create-repo` for the fullstack-ts template and verifies the output meets all quality bars.

**Tasks:**
- [ ] `Build eval runner` — `eval/run_eval.py` takes a template name (default: all implemented templates). For each template: creates a temp directory, runs the full pipeline (preflight → resolve → scaffold → verify), then runs additional structural checks. Reports pass/fail per check. Checks: expected directory structure (key files exist), package.json has expected dependencies, turbo.json has expected pipelines, CLAUDE.md exists at root and in each app/package, .claude/rules/ has testing.md + modules.md + types.md, biome.json has noExplicitAny, tsconfig has strict: true, at least one test file per app/package, docker-compose.yml exists with postgres service, .github/pull_request_template.md exists, seed script exists, Playwright config exists.
- [ ] `Build E2E eval check` — `eval/checks/check_e2e.py` goes beyond the basic verify: starts the full stack (docker + dev servers), runs `pnpm db:seed`, hits the API for users (GET /api/trpc/user.list), loads the frontend in Playwright and verifies it renders and can display data from the API. This is the "frontend calls backend" integration check.
- [ ] `Test eval framework` — Basic tests that the eval runner correctly reports pass/fail for a known-good scaffold output.

**Verify (after all tasks in phase):**
- [ ] `uv run python -m eval.run_eval --template fullstack-ts` runs and reports all checks pass
- [ ] The E2E check confirms frontend→backend→database round trip works

---

## Verification Commands

- `cd create-repo && uv sync && uv run pytest tests/ -v`
- `uv run python -m scripts.preflight --template fullstack-ts`
- `uv run python -m eval.run_eval --template fullstack-ts`

## Open Questions

- Jinja2 vs simpler string templating — Jinja2 is a dependency but gives us conditionals, loops, and includes for template composition. Worth it for the template complexity we'll have. If we want zero deps, Python's `string.Template` could work for simpler cases but gets painful with nested structures.
- Should the eval framework also test the `gh repo create` path, or always skip GitHub to keep evals self-contained? Leaning toward skip — test Git locally only.
- Playwright in the eval requires a headed or headless browser. Need to ensure `npx playwright install` is part of the scaffold or eval setup.

## Out of Scope

- Other templates (fullstack-graphql, fullstack-python, api-ts, api-python, swift-ts) — separate work items following the same pattern
- The solve-take-home skill — depends on create-repo being solid first
- Auth, state management, or other cross-cutting architectural concerns in templates
- The CLAUDE_HIVE auto-mode integration — future work item

## Lessons

<!-- Populated during the work by /hack and /learn. Each entry: what happened, what was learned, where it should go. -->
