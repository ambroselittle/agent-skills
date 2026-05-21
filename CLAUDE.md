# agent-skills

AI agent skills, hooks, and project templates for Claude Code. Skills are prompt-based tools that orchestrate workflows; hooks enforce safety rules on tool calls; templates scaffold new projects.

## Structure

```
skills/                # Skill definitions (SKILL.md + supporting files)
  ├── plan-work/          # Plan before building
  ├── do-work/            # Implement from a plan, commit, and open PR
  ├── code-review/        # Multi-agent parallel PR review (dialogic findings)
  ├── do-fixes/           # Apply fixes from a review, verify, commit, publish
  ├── plan-review/        # Expert review of implementation plans
  ├── create-repo/        # Monorepo scaffolding (Python scripts + Jinja2 templates)
  ├── solve-take-home/    # End-to-end take-home challenge solver
  ├── author-e2e/         # Playwright test generation from scenarios
  ├── make-skill/         # Interactive skill creator
  └── shared/             # Reusable agents, scripts (context.sh, get-diff.sh), references
hooks/
  └── PreToolUse/      # Rule-based allow/deny engine for tool calls
templates/             # CLAUDE.md guidance templates for ~/.claude/CLAUDE.md
setup.sh               # Idempotent installer: links skills, installs hooks, registers MCP
```

## Git workflow

- **Commit frequently, push rarely.** Each task gets its own commit for clean history, but only push when work is ready for review. Every push triggers CI — don't waste runs on intermediate states.
- **One push per completed phase or session** — not per commit.

## Skill anatomy

Every skill has a `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name
description: Short phrase shown to user
argument-hint: "[options]"
depends-on: plan-work           # optional prerequisite
context: fork                   # optional: run in isolated context
---
```

The rest of SKILL.md is the AI orchestrator prompt — phases, steps, and instructions for Claude Code. Skills may also include:
- `references/` — docs the skill reads at runtime (e.g., flakiness-practices.md)
- `agents/` — sub-agent definitions spawned by the skill
- `scripts/` — shell/Python utilities called by the skill
- `CLAUDE.md` — area-specific conventions (read this when working in that skill)

## Hook engine (hooks/PreToolUse/)

Rule-based engine that intercepts tool calls. Decision priority: **deny > ask > allow > proceed**.

Each rule in `rules.json` specifies an `operation` (e.g., `read-path`, `write-path`, `git-force-push`, `bash-safe`) and an `action`. See `hooks/PreToolUse/CLAUDE.md` for the full list of operations and how to add rules.

**Adding a new rule:**
1. Add the rule to `rules.json`
2. Create `tests/rules/test_<slug>.py` with `RULE_DESCRIPTION` matching the rule's `description` exactly
3. Include `test_match`, `test_no_match`, and at least one `test_boundary_*`
4. The convention checker (`test_verify_rule_conventions.py`) enforces this

## create-repo templates (skills/create-repo/)

Python scripts handle deterministic work; the AI handles intelligence (interview, version resolution, customization, diagnostics).

**Template layers:** up to 4 layers, each overriding the previous:
1. `templates/__common/` — universal files (all templates)
2. `templates/__common/<platform>/` — platform-specific shared files (e.g., `python/`, `ts/`)
3. `templates/<base>/` — base template files (when child declares `"extends"` in `template.json`)
4. `templates/<template>/` — template-specific files

Each template has a `template.json` declaring its platform (a string like `"python"` or a list like `["ts", "python"]` for multi-platform templates). When a list is given, each platform's `__common/<platform>/` layer is applied in order. Templates can inherit from a base via `"extends"` and skip specific base files via `"exclude"` globs. Files with `.j2` extension get Jinja2 rendering; others are copied as-is.

**Template variables:**
- `{{ project_name }}` — e.g., `my-app`
- `{{ scope }}` — e.g., `@my-app`
- `{{ swift_project_name }}` — PascalCase, e.g., `MyApp`
- `{{ versions.<key> }}` — resolved package versions

**Directory name templating:** Use `__variable_name__` in template directory names to substitute context variables at scaffold time. E.g., `Sources/__swift_project_name__/` becomes `Sources/MyApp/`. Unknown variables (like `__pycache__`) are left unchanged.

**Version key normalization:** npm names convert to underscore keys — `@scope/package` becomes `scope_package`. Strip `@`, replace `/`, `-`, `.` with `_`. Example: `@hono/node-server` → `hono_node_server`.

**Python project:** managed with uv. `cd skills/create-repo && uv sync --group dev` to set up.

## Testing

All Python projects use **uv** and **pytest**.

### Hook engine (~415 tests, <1s)
```bash
cd hooks/PreToolUse && uvx pytest tests/ -v
```

### create-repo unit + structural eval (~55 tests, <1s)
```bash
cd skills/create-repo && uv run pytest tests/ -v -m "not e2e"
```

### Scaffold E2E — interactive picker (needs pnpm, node, Docker or Postgres, ~3min)
```bash
make test-scaffolds                        # interactive — pick a template or all
make test-scaffolds TEMPLATE=fullstack-ts  # specific template
make test-scaffolds TEMPLATE=all           # all templates
```

In CI, set `DATABASE_URL` env var and the test auto-skips docker compose.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push to PR branches and main:
- **Unit tests** — hook engine + create-repo unit/structural (~30s)
- **Scaffold E2E** — scaffolds all templates, runs full verify pipeline with Postgres service container (~3min)

## Getting started

```bash
make init
```

This installs `uv` if missing, syncs Python environments (hooks + create-repo), and runs `setup.sh` to link skills and hooks. Run it once after cloning, or after switching to a new worktree.

## setup.sh

Called by `make init`. Idempotent installer that:
1. Links skills to `~/.claude/skills/` (worktree-aware — only changed skills in worktrees)
2. Installs PreToolUse hook engine to `~/.claude/hooks/`
3. Merges permissions from `built-in-rules.json` into `~/.claude/settings.json`
4. Registers MCP servers (Playwright)
5. Upserts guidance block into `~/.claude/CLAUDE.md` from `templates/`
