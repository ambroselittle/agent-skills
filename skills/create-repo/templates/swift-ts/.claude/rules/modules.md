## Module Conventions

### TypeScript (apps/api/, packages/)
- Use ES module imports (`import`/`export`), never CommonJS (`require`)
- Internal package imports use the workspace scope (e.g., `@my-app/db`)
- Barrel exports (`index.ts`) at package boundaries only, not within packages
- Prefer named exports over default exports
- Co-locate related code: keep types, utils, and tests near what they serve

### Swift (apps/mobile/)
- Use Swift's module system — import by module name, not file path
- Keep related types in the same file when they're tightly coupled
- Use extensions to organize conformances (e.g., `User+Codable` in the same file)
- Group files by feature: Models/, Views/, Services/
