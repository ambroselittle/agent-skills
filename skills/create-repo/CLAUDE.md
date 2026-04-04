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
│   ├── scaffold.py       # Jinja2 template renderer
│   ├── verify.py         # Build/test/lint verification suite
│   └── init_git.py       # Git init + GitHub repo creation
├── templates/            # Jinja2 template files
│   ├── common/           # Shared across all templates
│   └── fullstack-ts/     # React + Hono + tRPC + Prisma
├── tests/                # pytest tests for all scripts
└── eval/                 # Eval framework (TODO)
```

## How it works

The SKILL.md orchestrates the flow: interview → preflight → version resolution → scaffold → verify → git init. The Python scripts handle deterministic work (rendering templates, running verification commands). The AI handles intelligence work (version resolution via parallel agents, applying customizations, diagnosing failures).

## Running tests

```bash
cd create-repo && uv sync --group dev && uv run pytest tests/ -v
```

## Adding a new template

1. Create `templates/<template-name>/` with the template's files
2. Use `.j2` extension for files needing Jinja2 substitution
3. Available variables: `{{ project_name }}`, `{{ scope }}`, `{{ versions.<pkg> }}`
4. Add template-specific preflight checks to `TEMPLATE_CHECKS` in `preflight.py`
5. Add the template to the SKILL.md interview options
6. Write scaffold tests in `tests/test_scaffold.py`

## Template variable naming

For `versions.*` in Jinja2 templates, convert package names:
- `@scope/package` → `scope_package` (e.g., `@trpc/server` → `trpc_server`)
- `@scope/sub-package` → `scope_sub_package`
- Simple packages stay as-is (e.g., `react`, `hono`, `typescript`)
