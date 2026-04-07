---
name: zero-tolerance-lint
description: Templates must ship with zero lint/format deviations; verify.py enforces this; generated apps get warnings-as-errors by default
type: rule
---

## Zero-Tolerance Lint Policy for Templates

Scaffolded projects must be **completely clean** out of the box. The developer's first `pnpm lint`
or `ruff check` should produce zero output. They opt in to ignoring things — not the other way around.

### Two levels of strictness

| Context | Strictness |
|---|---|
| `verify.py` (our E2E) | Fail on any diagnostic — errors, warnings, **and info** |
| Generated app lint scripts | Fail on errors and warnings (`--error-on-warnings`) |

The info-level check belongs in `verify.py` only. We don't ship that extra strictness into the
developer's project — they get a clean, passing baseline with warnings-as-errors and can decide
from there.

### TypeScript / Biome

- Generated `lint` script: `biome check --error-on-warnings .`
- Generated `lint:fix` script: `biome check --write .`
- `verify.py` lint step uses `fail_on_output=[r"Found \d+ (error|warning|info)"]` — catches infos
  that biome reports without a non-zero exit
- **Never add `// biome-ignore` to work around a template issue** — fix the root cause

### Python / Ruff

- `ruff check` is already binary (any violation = non-zero exit, no warning level)
- `ruff format --check` is **fatal** in verify.py — templates must be fully formatted
- Setup runs `ruff format .` to normalize any generation-time formatting drift before verify
- **Never add `# noqa` to work around a template issue** — fix the root cause

### Fixing a lint issue in a template

When a template produces a lint violation:
1. Fix the template source — don't suppress
2. If the violation is in generated/third-party code (e.g., Prisma output), add the narrowest
   possible suppression (`// biome-ignore rule: reason` or `# noqa: EXXXX`) with a comment
3. Re-run `make test-scaffolds TEMPLATE=<name>` to confirm clean
