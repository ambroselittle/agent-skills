# Design Philosophy

How to think about architecture when building solutions. Read this before proposing an architecture — it defines the perspective you're designing from.

## Framing

Treat every solution as **V1 of a real application that will grow**. Not a throwaway prototype, not an enterprise system — a well-considered starting point that a team could pick up and extend. The fact that it's a take-home evaluation is incidental. The goal is to show how you would actually build a real app starting from these requirements.

## Core principles

### Domain coherence over technology layers

Group code by what it does, not what it is. A todo module with its routes, logic, and data access together is better than scattering todo concerns across `controllers/`, `services/`, and `repositories/` directories. The meaningful boundaries are between domains (todos, auth, payments), not between technologies (routes, middleware, models).

### Layers earn their existence

Every layer of indirection must solve a real problem — testability, isolating genuinely complex business rules, a real need for swappability. If the justification is "best practices say so," the layer doesn't belong. Three lines of validation in a route handler don't need a `ValidationService`. A database you'll never swap doesn't need a repository interface just for the sake of abstraction.

Ask: **what problem does this layer solve that I'd actually hit?** If the answer is "none right now, but maybe someday" — skip it.

### Pragmatic colocation

CSS-in-JS, JSX with logic, styled components, inline handlers — all fine. The meaningful separation is between concerns that genuinely need to vary independently, not between technologies. A React component with its styles, event handlers, and data fetching is one cohesive unit, not three concerns crammed together.

### Frontend logic is a feature, not a flaw

Putting validation, formatting, or lightweight business logic on the frontend for UX responsiveness is a reasonable tradeoff. Instant client-side feedback is better UX than round-tripping to a server. This isn't a violation of "single source of truth" — it's pragmatic layering where the frontend optimistically validates and the backend authoritatively enforces.

### Structure for the next feature, not the tenth

Since we're framing this as V1 of a growing app: design so the next developer (or the next feature) can extend naturally. That means clear module boundaries, consistent patterns within each module, and enough structure that someone reading the code understands where new things go. But don't design for ten features from now — that's speculative architecture.

## What this means in practice

**Do:**
- Separate business logic from HTTP concerns when the logic is non-trivial
- Use a data access layer when it improves testability (even a thin one)
- Keep route handlers focused on request/response — delegate to domain functions
- Collocate related code (a feature's routes, types, logic, and tests together)
- Use consistent patterns within the codebase — if one module has a service, they all should
- Encode architectural decisions in `CLAUDE.md` and `.claude/rules/` — if a convention matters enough to follow, it matters enough to write down where both humans and AI agents will find it

**Don't:**
- Add a repository interface over a database you're not swapping
- Extract a service that just passes data through to the data layer
- Separate CSS/JS/HTML into different directories for "separation of concerns"
- Add dependency injection frameworks when constructor parameters work fine
- Create catch-all `utils/` or `helpers/` at the repo root as a junk drawer for unrelated code — find a meaningful home in the relevant domain module instead. Note: `__common/` within a feature area for legitimately shared code is fine (the leading underscores keep it visually sorted to the top), and a top-level `shared/` or `common/` for cross-feature components is fine when it's intentional
- In React codebases: mix component exports and non-component exports (hooks, utilities, constants) in the same file — this breaks HMR in Vite/Vitest. Keep components in their own files.
