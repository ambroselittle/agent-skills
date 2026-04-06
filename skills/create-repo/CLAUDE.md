# create-repo skill

Project scaffolding skill that bootstraps monorepo projects from templates.

## Structure

```
create-repo/
├── SKILL.md              # AI orchestrator — the skill definition
├── CLAUDE.md             # This file
├── pyproject.toml        # Python project config (uv-managed)
├── scripts/              # Python modules called by the skill
│   ├── preflight.py      # Environment checker (tools, versions)
│   ├── scaffold.py       # Jinja2 template renderer (3-layer)
│   ├── verify.py         # Build/test/lint verification (platform-aware)
│   └── init_git.py       # Git init + GitHub repo creation
├── templates/            # Jinja2 template files
│   ├── __common/         # Universal files (all templates)
│   │   ├── python/       # Shared across Python templates
│   │   └── ts/           # Shared across TypeScript templates
│   ├── fullstack-ts/     # React + Hono + tRPC + Prisma
│   ├── fullstack-graphql/ # React + Hono + Yoga/Pothos + Apollo + Prisma
│   └── api-python/       # FastAPI + SQLModel + Postgres
├── tests/                # pytest tests for all scripts
└── eval/                 # Eval framework
```

## How it works

The SKILL.md orchestrates the flow: interview → preflight → version resolution → scaffold → verify → git init. The Python scripts handle deterministic work (rendering templates, running verification commands). The AI handles intelligence work (version resolution via parallel agents, applying customizations, diagnosing failures).

## Template layers

Templates render in 3 layers, each overriding the previous:
1. `__common/` — universal files (docker-compose, .gitignore, PR template, etc.)
2. `__common/<platform>/` — platform-specific shared files (e.g., ruff config for Python, biome for TS)
3. `<template>/` — template-specific files

Each template has a `template.json` declaring its platform (e.g., `{"platform": "python"}`). The scaffold engine reads this to determine which platform layer to include.

## Running tests

```bash
cd create-repo && uv sync --group dev && uv run pytest tests/ -v
```

## Adding a new template

1. Create `templates/<template-name>/` with the template's files
2. Add `template.json` with `{"platform": "<platform>"}` (e.g., "python", "ts")
3. Add shared platform files to `__common/<platform>/` if they don't exist yet
4. Use `.j2` extension for files needing Jinja2 substitution
5. Available variables: `{{ project_name }}`, `{{ scope }}`, `{{ versions.<pkg> }}`
6. Add template-specific preflight checks to `TEMPLATE_CHECKS` in `preflight.py`
7. Add template to `AVAILABLE_TEMPLATES` and version fallbacks in `eval/run_eval.py`
8. Add structural checks to `eval/checks/check_structure.py`
9. Add the template to the SKILL.md interview options
10. Write scaffold tests in `tests/test_scaffold.py`

## Template variable naming

For `versions.*` in Jinja2 templates, convert package names:
- `@scope/package` → `scope_package` (e.g., `@trpc/server` → `trpc_server`)
- `@scope/sub-package` → `scope_sub_package`
- Simple packages stay as-is (e.g., `react`, `hono`, `fastapi`)

## Platform detection

`verify.py` and `check_structure.py` detect the platform from the scaffolded output:
- `pyproject.toml` present → Python (uv sync, ruff, pytest, uvicorn)
- `package.json` present → Node (pnpm install, biome, turbo, vitest)
