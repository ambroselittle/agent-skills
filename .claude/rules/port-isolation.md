## Port Isolation in Scaffolded Templates

Every template that starts a local service (database, API server, web server) **must** use dynamic port discovery — never hardcode port numbers in any file that gets deployed to the developer's machine.

### Why

Developers run multiple projects simultaneously. Hardcoded ports (5432, 8000, 3000) collide silently — docker fails, connections are refused, and debugging takes longer than the original scaffolding.

### Requirements for every stack template

**1. A `setup` command that discovers free ports and writes `.env`**
- TS templates: `scripts/discover-ports.ts` → `.env.ports` + per-package `.env` files
- Python templates: `scripts/setup.py` → root `.env` + `apps/api/.env`
- Port ranges: DB 5432–5499, API 8000–8099 (Python) / 3100–3199 (TS), Web 3000–3099
- Both scripts use a global port registry at `~/.agent-skills/.port-registry.json` to avoid collisions when multiple scaffolding runs happen concurrently (locked via a lock file — `fcntl.LOCK_EX` on Python, `openSync('wx')` on TS)

**2. `docker-compose.yml` must use `${DB_PORT:-5432}:5432`**
- The host-side port is variable; the container-side is always 5432
- `${DB_PORT:-5432}` means docker-compose reads `DB_PORT` from `.env`

**3. The `start` command must handle conflicts gracefully**
- Auto-run `setup` if `.env` is missing (first run)
- Before starting docker, check if `$DB_PORT` is already taken by a non-owned process
- If taken, re-run `setup` to discover new ports, then proceed
- Pattern for Python justfiles:
  ```bash
  if [ ! -f .env ]; then just setup; fi
  set -a; source .env; set +a
  if ! python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.bind(('', ${DB_PORT:-5432})); s.close()" 2>/dev/null; then
      if ! docker compose ps --quiet postgres 2>/dev/null | grep -q .; then
          just setup && set -a && source .env && set +a
      fi
  fi
  ```

**4. `set dotenv-load := true` in justfiles**
- Ensures all just recipes automatically inherit env vars from `.env`
- Means `db-migrate` gets `DATABASE_URL` without manual env var passing

**5. No hardcoded ports anywhere in templates**
- `alembic.ini`: the fallback `localhost:5432` is acceptable as a static default — it's overridden by `DATABASE_URL` env var in `alembic/env.py`
- `database.py`: `DATABASE_URL` env var fallback to `localhost:5432` is acceptable — setup.py writes the real URL before `just start`
- Never hardcode ports in CI workflows — CI uses `DATABASE_URL` env var directly

### Verification

`verify.py` runs `scripts/setup.py` (for Python) or `pnpm project:setup` (for TS) before starting docker-compose. This ensures the correct port is in `.env` before the stack starts.
