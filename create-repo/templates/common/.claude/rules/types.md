## TypeScript Conventions

- `strict: true` in all tsconfig files — no exceptions
- No `any` — use `unknown` and narrow, or define a proper type
- Prefer interfaces for object shapes, types for unions/intersections
- Shared types go in `packages/types/`
- API response types should be inferred from the router/handler, not manually duplicated
- Use Prisma-generated types for database models — don't redefine them
