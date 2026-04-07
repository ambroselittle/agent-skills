## Type Conventions

### TypeScript (apps/web/)
- `strict: true` in all tsconfig files — no exceptions
- No `any` — use `unknown` and narrow, or define a proper type
- Prefer interfaces for object shapes, types for unions/intersections

### Python (apps/api/)
- Type hints on all function signatures — parameters and return types
- Use modern syntax: `str | None` not `Optional[str]`, `list[int]` not `List[int]`
- Use Pydantic models for request/response validation, SQLModel for database models
- Avoid `Any` — use `object` or a protocol when the type is genuinely unknown
- SQLModel fields use `Field()` for metadata (primary_key, index, default, etc.)
