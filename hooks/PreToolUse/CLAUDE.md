# PreToolUse Hook Engine

A rule-based engine that intercepts Claude Code tool calls before execution and returns
allow/deny/ask decisions.

## Architecture

```
pre-tool-use.sh          # Entry point (registered in settings.json)
  └─ engine/
       ├─ interpreter.py  # Reads stdin JSON, loads rules, calls evaluate()
       ├─ engine.py       # Core evaluator: runs all rules, applies priority
       ├─ resolver.py     # Path normalization and glob matching
       └─ operations/     # Per-operation matchers
            ├─ common.py      # Shared utilities (_tokenize, _split_subcommands)
            ├─ bash.py        # bash-safe (denylist of unsafe commands)
            ├─ filesystem.py  # read-path, write-path, delete-path
            ├─ git.py         # git-force-push, git-reset-hard, git-push-direct
            └─ gh.py          # gh-pr-merge, gh-api
```

## Decision Priority

All rules are evaluated against every tool call. The highest-priority match wins:

1. **deny** — block the tool call, return reason
2. **ask** — prompt the user for confirmation
3. **allow** — permit silently (no prompt)
4. **proceed** — no rule matched; defer to Claude Code's built-in permissions

## Rule Types

Rules in `rules.json` match by either:
- **`operation`** — a named operation handler (e.g. `read-path`, `git-force-push`, `bash-safe`)
- **`pattern`** — a regex matched against Bash commands or file paths

## Adding a New Rule

1. Add the rule to `rules.json` with a unique `description`
2. Create `tests/rules/test_<slug>.py` with `test_match`, `test_no_match`, and at least one `test_boundary*`
3. Set `RULE_DESCRIPTION` in the test to match the rule's `description` exactly
4. Run `uvx pytest hooks/PreToolUse/tests/` — the convention checker will catch missing tests

Slug derivation: lowercase, hyphens, truncated at first `—` or `(`.

## Testing

```bash
uvx pytest hooks/PreToolUse/tests/ -v
```

`test_verify_rule_conventions.py` enforces that every rule has a test file with the required functions.
