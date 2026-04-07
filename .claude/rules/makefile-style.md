---
paths: ["**/Makefile", "**/Makefile.*", "**/*.mk"]
---

## Makefile conventions

- Prefix all recipe commands with `@` to suppress command echo — the user cares about output, not the command that produced it.
- Start each target with a `printf` label (cyan, `\033[36m`) so the user knows what's running. Keep labels short and action-oriented (e.g., "Linting...", "Testing hook engine...").
- Exception: don't silence commands that take user-provided arguments (e.g., `$(TEMPLATE)`) where seeing the full invocation helps debug wrong inputs.
