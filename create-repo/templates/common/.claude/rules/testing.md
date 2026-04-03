## Testing Standards

- Every app and package must have at least one test file
- Use Vitest for TypeScript tests, pytest for Python
- Test files live in `__tests__/` directories or `tests/` (Python)
- Name test files `*.test.ts`, `*.test.tsx`, or `test_*.py`
- Write tests that verify behavior, not implementation
- Mock external services, not internal modules
- Integration tests should use real database connections where possible
