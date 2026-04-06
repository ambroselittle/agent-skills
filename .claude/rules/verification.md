## Verification Before Completion

Before reporting any work item as done, **all** of the following must pass — not just the tests related to your changes:

1. **Unit tests:** `make test` (hook engine + create-repo unit/structural)
2. **Scaffold E2E:** `make test-scaffolds TEMPLATE=all` (all templates — fullstack-ts, api-python, and any future templates)

Do not tell the user work is complete until you have run both commands and confirmed zero failures. If something fails, fix it — regardless of whether your changes caused it. A green test suite is the deliverable, not just your diff. If you've made 5 genuine attempts to fix a failure and it's still broken, report what you've tried and what you're seeing.
