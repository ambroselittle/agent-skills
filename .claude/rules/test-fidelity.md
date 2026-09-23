## Test Fidelity: Test What Users Actually Run

The scaffold E2E verification pipeline must exercise the exact same commands and entry points that a developer uses after the template runs. This applies to **every out-of-the-box script** the template exposes — not just `start`, but also `test`, `lint`, `format`, `build`, and any other recipe or script in the scaffolded project.

### Why this matters

Alternative invocations may succeed in tests while masking real failures:

- Different PATH environments (pnpm scripts add `node_modules/.bin`; bare bash does not)
- Signal handling and exit behavior that only goes through the user-facing script
- Port conflict detection, setup auto-run, and other task-runner logic that is bypassed entirely
- Wrapper behavior in justfile recipes, pnpm scripts, or turbo pipelines that the direct command skips

A test that passes via a shortcut gives false confidence. The whole point of the E2E pipeline is to ensure that when a scaffolded project lands on a developer's machine, the commands they're told to run actually work.

### Rule

**Every command the template documents or exposes must be called the same way in verify.py as a developer would call it.** If `just test` is what the CLAUDE.md says to run, verify.py must call `just test` — not `uv run pytest` directly. If `pnpm lint` is the documented lint command, verify.py must call `pnpm lint` — not `npx biome check` or individual tool invocations.

| Template type | Lint | Test | Start |
|---|---|---|---|
| fullstack-python | `just lint` or `uv run ruff` / `pnpm lint` as documented | `just test` or per-app as documented | `just start` |
| Python (api-python) | `just lint` / `uv run ruff` | `just test` / `uv run pytest` | `just start` |
| TS templates | `pnpm lint` | `pnpm test` | `pnpm start` |

When the template's task runner wraps a tool (e.g., `just test` calls `uv run pytest`), the verify pipeline must call the wrapper — not the underlying tool — so that any bugs in the wrapper are caught.

### CI compatibility

If the user-facing start command manages infrastructure (e.g., docker compose), add a guard for CI environments where that infrastructure is provided externally. The canonical pattern: treat `DATABASE_URL` as external, and skip docker, only when it does not point at `localhost:$DB_PORT` from setup. Capturing `DATABASE_URL` before sourcing `.env` is not enough, because `set dotenv-load` has already exported `.env` when the recipe starts. This keeps the command identical for users while making it safe to call in CI.

Setup leaves infrastructure running, which hides a start command that never starts it. Locally, `verify.py` stops the project's Postgres before `just start` and then lists users through the API, so the check covers what a developer sees on every run after the first.

Never add a separate `start-ci` recipe or bypass flag — that defeats the purpose and creates two diverging code paths.
