## Module Conventions

### TypeScript (apps/web/)
- Use ES module imports (`import`/`export`), never CommonJS (`require`)
- Prefer named exports over default exports
- Co-locate related code: keep types, utils, and tests near what they serve

### Python (apps/api/)
- Use absolute imports from the package root (e.g., `from src.models import User`)
- Every package directory must have an `__init__.py` (can be empty)
- Avoid circular imports — extract shared types to a third module if needed
- Group imports: stdlib → third-party → local, separated by blank lines
