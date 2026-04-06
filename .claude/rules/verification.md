## Verification Before Completion

Before reporting any work item as done, **all** of the following must pass — not just the tests related to your changes:

1. **Unit tests:** `make test` (hook engine + create-repo unit/structural)
2. **Scaffold E2E:** `make test-scaffolds TEMPLATE=all` (all templates — fullstack-ts, api-python, and any future templates)

Do not tell the user work is complete until you have run both commands and confirmed zero failures. If something fails, diagnose and fix it before reporting — or explain what's broken and why if it's outside the scope of the current work.
