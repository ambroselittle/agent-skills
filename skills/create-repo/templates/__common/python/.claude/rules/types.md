## Python Type Conventions

- Type hints on all function signatures — parameters and return types
- Use modern syntax: `str | None` not `Optional[str]`, `list[int]` not `List[int]`
- Use Pydantic models for request/response validation, SQLModel for database models
- Avoid `Any` — use `object` or a protocol/type var when the type is genuinely unknown
- Use `from __future__ import annotations` for forward references when needed
- SQLModel fields use `Field()` for metadata (primary_key, index, default, etc.)
