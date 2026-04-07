---
name: zero-tolerance-lint
description: Templates must ship with zero lint/format deviations — errors, warnings, and info all fail
type: rule
---

## Zero-Tolerance Lint Policy

Scaffolded projects must be **completely clean** out of the box. The developer's first `pnpm lint`
or `ruff check` should produce zero output. They opt in to ignoring things — not the other way around.

### TypeScript / Biome

- The `lint` script uses `scripts/biome-check.sh`, which runs `biome check --error-on-warnings`
  **and** inspects output for any `Found N (error|warning|info)` line
- `lint:fix` uses plain `biome check --write` for auto-repair
- `verify.py` applies the same `fail_on_output` pattern to the lint step
- **Never add biome suppress comments to work around a template issue** — fix the root cause

### Python / Ruff

- `ruff check` is already strict (any violation = non-zero exit)
- `ruff format --check` is **fatal** in verify.py — templates must be formatted
- Setup runs `ruff format .` before verify to normalize generation-time drift
- **Never add `# noqa` to work around a template issue** — fix the root cause

### Adding a new rule exception

If a generated project legitimately needs to suppress a lint rule for a specific line (e.g., a
Prisma-generated file, a framework-required pattern), use the narrowest suppression possible
(`// biome-ignore rule: reason` or `# noqa: EXXXX`) and only after confirming the issue cannot
be fixed structurally. Document why in a comment.
