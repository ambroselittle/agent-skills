## Dependency Version Policy

- **Never use unpinned versions** like `"latest"`, `"*"`, or unbounded ranges in package.json or pyproject.toml
- All dependencies must specify a version — use exact (`1.2.3`), caret (`^1.2.3`), tilde (`~1.2.3`), or bounded ranges (`>=1.2,<2`)
- `workspace:*` is fine — it's a workspace protocol reference, not a version
- When adding a new dependency, resolve the current stable version and pin it
- Unpinned versions cause non-reproducible builds, broken CI, and silent regressions when upstream packages release breaking changes
