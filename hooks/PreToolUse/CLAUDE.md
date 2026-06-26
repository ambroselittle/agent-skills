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
            ├─ filesystem.py  # read-path, write-path, write-content, delete-path
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

### Path matching is case-insensitive by default

macOS filesystems are case-insensitive — `.ENV` and `.env` are the same file — so exact-case
matching would let casing bypass every path-based rule. All `paths` globs on filesystem
operations (`read-path`, `write-path`, `write-content`, `delete-path`) therefore match
case-insensitively. A rule can opt out with `"case-sensitive": true`.

## Adding a New Rule

1. Add the rule to `rules.json` with a unique `description`
2. Create `tests/rules/test_<slug>.py` with `test_match`, `test_no_match`, and at least one `test_boundary*`
3. Set `RULE_DESCRIPTION` in the test to match the rule's `description` exactly
4. Run `uvx pytest hooks/PreToolUse/tests/` — the convention checker will catch missing tests

Slug derivation: lowercase, hyphens, truncated at first `—` or `(`.

## Personal machine-local overlay

`~/.agent-skills/local-rules.json` is a personal, uncommitted source of
**additive** rules, merged into the global set at evaluation time
(`load_user_local_rules` in `engine.py`, wired in `interpreter.py`). Use it for
private rules — e.g. org- or employer-specific command blocks — that should not
live in this shared repo. The file mirrors the per-repo override shape, but its
entries are full rule objects rather than relax-only overrides:

```json
{
  "hooks": {
    "PreToolUse": {
      "rules": [
        {
          "id": "lc-block-prod-aws-profile",
          "pattern": "(?:--profile[=\\s]+|AWS_PROFILE=)production-",
          "action": "deny",
          "reason": "prod access is human-initiated only"
        }
      ]
    }
  }
}
```

Overlay rules are exempt from the `rules.json` convention checker (they are not
in this repo) and fail open if the file is absent or malformed. Distinct from
the per-repo `.agent-skills/config.json`, which only _relaxes_ existing denies.

## Testing

```bash
uvx pytest hooks/PreToolUse/tests/ -v
```

`test_verify_rule_conventions.py` enforces that every rule has a test file with the required functions.
