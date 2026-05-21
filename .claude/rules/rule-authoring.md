---
paths: [".claude/rules/**"]
---

## Writing Rules: Scope Before You Save

When creating a new rule in `.claude/rules/`, always ask: **does this only matter when working on specific file types or directories?**

If yes, add a `paths` frontmatter to scope it — this keeps the always-loaded context lean and avoids injecting irrelevant rules into unrelated work.

```markdown
---
paths: ["**/pyproject.toml", "**/*.toml"]
---
```

**Scope it when the rule applies to:**
- A specific file type (`.toml`, `Makefile`, `*.tsx`, `*.py`, etc.)
- A specific directory or subtree (`apps/api/**`, `hooks/**`, `skills/*/SKILL.md`)
- A specific tool or framework only used in certain files

**Leave it unscoped (always loaded) when:**
- It governs general behavior across all work (e.g., scope philosophy, verification policy)
- You can't reliably predict which file types will trigger it
- It's a process rule, not a code pattern rule (e.g., "never merge unless asked")

**Examples from this repo:**
- `makefile-style.md` → scoped to `**/Makefile`
- `python-packaging.md` → scoped to `**/pyproject.toml`
- `zero-tolerance-lint.md` → unscoped (applies to all template work regardless of file)
- `scope-philosophy.md` → unscoped (governs behavior, not file content)
