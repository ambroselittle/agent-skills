## Dependency Version Policy

- **Never use unpinned versions** like `"latest"`, `"*"`, or unbounded ranges in package.json or pyproject.toml
- All dependencies must specify a bounded version
- Unpinned versions cause non-reproducible builds, broken CI, and silent regressions when upstream packages release breaking changes

### package.json (Node/TypeScript)
- Use exact (`1.2.3`), caret (`^1.2.3`), or tilde (`~1.2.3`)
- `workspace:*` is fine — it's a workspace protocol reference, not a version

### pyproject.toml (Python)
- Use compatible release `~=` (e.g., `fastapi~=0.115.0` — allows `>=0.115.0,<0.116`)
- Or explicit bounded ranges (e.g., `fastapi>=0.115.0,<1`)
- Never bare `>=` without an upper bound — a major version bump could silently break the project
- `requires-python = ">=3.12"` is fine — that's a language version constraint, not a package dep
