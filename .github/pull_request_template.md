## Summary

<!-- What changed and why. Link issues with "Closes #N". -->

## Verification

<!-- Delete sections that don't apply to your changes. -->

### Skills
- [ ] Manually ran the modified skill(s) end-to-end and confirmed expected behavior
- [ ] Tested edge cases (missing args, bad input, partial state)

### Hooks (PreToolUse)
- [ ] Manually triggered the hook rule and confirmed it fires correctly (deny/ask/allow)
- [ ] Confirmed non-matching cases pass through (no false positives)
- [ ] `cd hooks/PreToolUse && uvx pytest tests/ -v` — all passing

### Templates (create-repo)
- [ ] Unit + structural tests: `cd skills/create-repo && uv run pytest tests/ -v -m "not e2e"`
- [ ] Scaffold E2E for affected templates: `make test-scaffolds TEMPLATE=<name>`
- [ ] Scaffold E2E for all templates: `make test-scaffolds TEMPLATE=all`
- [ ] Added or updated tests for new/changed behavior

### Setup / CI / Infra
- [ ] Ran `setup.sh` on a clean state and confirmed it completes without errors
- [ ] Verified CI workflow changes with a test push or `act` dry run
