#!/usr/bin/env bash
# Run biome check and fail on any diagnostic output — errors, warnings, or info.
# Biome exits 0 even with info-level diagnostics, so we inspect the output.

set -euo pipefail

output=$(npx biome check --error-on-warnings "$@" 2>&1) || {
  echo "$output"
  exit 1
}

echo "$output"

if echo "$output" | grep -qE 'Found [0-9]+ (error|warning|info)'; then
  echo "biome: diagnostic output detected — treat as error for zero-tolerance lint"
  exit 1
fi
