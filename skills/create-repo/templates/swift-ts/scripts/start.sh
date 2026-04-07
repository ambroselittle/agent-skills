#!/usr/bin/env bash
# Start the full dev stack: Postgres + API server + open Xcode.
# Tears down Docker cleanly on exit (Ctrl+C).

set -euo pipefail
docker compose up -d

# Ignore SIGINT in this script — turbo and its children handle it.
# After turbo exits, we clean up Docker.
trap '' INT
set +e

FORCE_COLOR=1 turbo dev 2>&1 | grep -v "run failed"

echo ""
echo "Shutting down..."
docker compose down 2>/dev/null
