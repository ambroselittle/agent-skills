## Default Stack Preferences

When scaffolding greenfield projects or choosing technologies, default to these unless the user specifies otherwise.

### Monorepo & Build
- pnpm + Turborepo for TS orchestration, uv workspaces for Python
- just as polyglot task runner for mixed-language repos
- Vite for build/dev, Vitest for TS testing, pytest for Python
- Biome for TS linting/formatting, Ruff for Python

### Frontend (TS)
- React (latest) + Tailwind CSS v4 + shadcn/ui
- Apollo Client for GraphQL projects

### Backend (TS)
- Hono (runs on any runtime — Node, Deno, Bun, edge)
- tRPC as default for TS-to-TS (monorepo frontend-backend)
- GraphQL (Yoga + Pothos) when multi-client or prompt specifies
- REST for public/external APIs
- Prisma ORM + PostgreSQL (docker-compose for local dev)

### Backend (Python)
- FastAPI + uv + SQLModel/SQLAlchemy + Alembic
- Ruff for linting/formatting, pytest + httpx for testing

### Mobile (Swift)
- Xcode CLI tooling (xcodegen or similar)
- Multi-platform: iOS, iPadOS, Designed for iPad (Mac), visionOS
- REST + OpenAPI spec for typed Swift client generation
- Not Supabase — prefers portable Hono + Prisma + Postgres

### API Communication
- tRPC: same-monorepo TS frontend/backend
- GraphQL: multiple clients or cross-language
- REST: public APIs or when specified
- OpenAPI spec: cross-language typed clients (e.g., Swift)

### Database
- PostgreSQL as default (JSONB for mixed mode)
- docker-compose for local dev
- MySQL only as explicit exception

### Principles
- Match market traction for tool choices (greenfield direction, not legacy install base)
- Always git init + first commit after scaffold
- Always include test scaffolding
- Default to creating GitHub repo (gh repo create), allow opt-out
- Auth and cross-cutting concerns are separate, not part of initial scaffolding
