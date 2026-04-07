## Skill ↔ Test Parity

The create-repo skill and the scaffold E2E tests (`make test-scaffolds`) MUST use the exact same
verification pipeline. `verify.py` is the single source of truth for post-scaffold steps (install,
db setup, build, lint, test, dev server, e2e). The skill calls `verify.py`. The tests call
`verify.py`. No divergence.

If a step needs to happen after scaffolding, it goes in `verify.py` — not in SKILL.md prose, not
in a separate script, not "the AI will figure it out." The AI's job is interview + version
resolution + diagnostics. Everything deterministic is a script.
