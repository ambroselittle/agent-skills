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
│   ├── scaffold.py       # Jinja2 template renderer (layered, with extends)
│   ├── verify.py         # Build/test/lint verification (platform-aware)
│   └── init_git.py       # Git init + GitHub repo creation
├── templates/            # Jinja2 template files
│   ├── __common/         # Universal files (all templates)
│   │   ├── python/       # Shared across Python templates
│   │   └── ts/           # Shared across TypeScript templates
│   ├── fullstack-ts/     # React + Hono + tRPC + Prisma (base for TS templates)
│   ├── fullstack-graphql/ # React + Hono + Yoga/Pothos + Apollo + Prisma (extends fullstack-ts)
│   ├── api-ts/           # Hono + tRPC + Prisma, no frontend (extends fullstack-ts)
│   ├── api-python/       # FastAPI + SQLModel + Postgres
│   ├── fullstack-python/ # React + FastAPI + Postgres (extends fullstack-ts, multi-platform)
│   └── swift-ts/         # Swift multiplatform + Hono REST API (extends fullstack-ts)
├── tests/                # pytest tests for all scripts
└── eval/                 # Eval framework
```

## How it works

The SKILL.md orchestrates the flow: interview → preflight → version resolution → scaffold → verify → git init. The Python scripts handle deterministic work (rendering templates, running verification commands). The AI handles intelligence work (version resolution via parallel agents, applying customizations, diagnosing failures).

## Template layers

Templates render in up to 4 layers, each overriding the previous:
1. `__common/` — universal files (docker-compose, .gitignore, PR template, etc.)
2. `__common/<platform>/` — platform-specific shared files (e.g., ruff config for Python, biome for TS)
3. `<base_template>/` — base template files (when `"extends"` declared in template.json, with `"exclude"` globs applied)
4. `<template>/` — template-specific files

Each template has a `template.json` declaring its platform (e.g., `{"platform": "python"}` or `{"platform": ["ts", "python"]}` for multi-platform templates) and optionally `"extends"` + `"exclude"`. When platform is a list, each `__common/<platform>/` layer is applied in order (later overrides earlier). The scaffold engine reads this to determine which layers to include.

## Running tests

```bash
cd create-repo && uv sync --group dev && uv run pytest tests/ -v
```

## Adding a new template

1. Create `templates/<template-name>/` with the template's files
2. Add `template.json` with `{"platform": "<platform>"}` (e.g., `"python"`, `"ts"`, or `["ts", "python"]` for multi-platform)
   - To inherit from an existing template, add `"extends": "<base-template>"` and only include files that differ
   - Use `"exclude": ["pattern/**"]` to skip base template files (fnmatch globs)
3. Add shared platform files to `__common/<platform>/` if they don't exist yet
4. Use `.j2` extension for files needing Jinja2 substitution
5. Available variables: `{{ project_name }}`, `{{ scope }}`, `{{ swift_project_name }}` (PascalCase), `{{ versions.<pkg> }}`
6. Add template-specific preflight checks to `TEMPLATE_CHECKS` in `preflight.py`
7. Add template to `AVAILABLE_TEMPLATES` and version fallbacks in `eval/run_eval.py`
8. Add structural checks to `eval/checks/check_structure.py`
9. Add the template to the SKILL.md interview options
10. Write scaffold tests in `tests/test_scaffold.py`

## Directory name templating

Use `__variable_name__` in template directory names to substitute context variables at scaffold time. For example, `Sources/__swift_project_name__/` becomes `Sources/MyApp/` when the project name is `my-app`. Unknown variables (like `__pycache__`) are left unchanged.

## Template variable naming

For `versions.*` in Jinja2 templates, convert package names:
- `@scope/package` → `scope_package` (e.g., `@trpc/server` → `trpc_server`)
- `@scope/sub-package` → `scope_sub_package`
- Simple packages stay as-is (e.g., `react`, `hono`, `fastapi`)

## Platform detection

`verify.py` and `check_structure.py` detect the platform from the scaffolded output:
- Both `pyproject.toml` and `package.json` present → fullstack-python (combined: uv + pnpm, ruff + biome, pytest + vitest, both dev servers)
- `pyproject.toml` only → Python (uv sync, ruff, pytest, uvicorn)
- `package.json` only → Node (pnpm install, biome, turbo, vitest)
