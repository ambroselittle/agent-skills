## Type Conventions

### TypeScript (apps/api/, packages/)
- `strict: true` in all tsconfig files — no exceptions
- No `any` — use `unknown` and narrow, or define a proper type
- Prefer interfaces for object shapes, types for unions/intersections
- Shared types go in `packages/types/`
- Use Prisma-generated types for database models — don't redefine them

### Swift (apps/mobile/)
- Use `Codable` for all API models — match the JSON structure from the REST API
- Prefer value types (`struct`) over reference types (`class`) for models
- Use `@Observable` (iOS 17+) for view models, not `ObservableObject`
- Use Swift's strict concurrency (`actor`, `Sendable`) for shared mutable state
- All API methods should be `async throws`
