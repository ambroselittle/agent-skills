# MessageDisplay Hook — Phrase Swap

Swaps tired phrases out of Claude's on-screen text as it streams. `load-bearing`
becomes `important`, `you're absolutely right` becomes `you're right`.

Inspired by [Jola's post](https://jola.dev/posts/how-to-stop-claude-from-saying-load-bearing),
minus the joke replacements.

## What it can and can't do

**Display-only.** Claude Code renders `displayContent` in place of the delta but stores
the original in the transcript and sends the original to the model. So this changes what
you read — it does not change what Claude writes, and it never leaks back into context.
The model is none the wiser and will keep saying "load-bearing"; you just stop seeing it.

If you want Claude to actually stop *producing* a phrase, that's a prompt change
(`templates/user-claude.md`), not a hook. The two are complementary.

## Architecture

```
swap.py          # The whole hook: reads a delta on stdin, prints the replacement
phrases.json     # Shipped word list ("swaps"), plus off-by-default "suggestions"
tests/           # uvx pytest tests/
```

There is deliberately **no bash entry point** here, unlike `PreToolUse/` and
`Notification/`. Claude Code awaits this hook before painting each delta, and dropping
the wrapper process takes a flush from ~50ms to ~36ms. `swap.py` is registered directly
(shebang + `chmod +x`).

## The hook contract

Fires with each batch of newly completed lines while an assistant message streams —
many times per message, not once.

```jsonc
// stdin
{"messageId": "...", "index": 0, "final": false, "delta": "...whole lines..."}

// stdout — omit entirely to display the original
{"hookSpecificOutput": {"hookEventName": "MessageDisplay", "displayContent": "..."}}
```

`index` counts flushes within a message; `final` marks the last one (and is the only
flush whose delta may end mid-line). Every failure path — bad JSON, missing phrases
file, an unexpected exception — exits 0 in silence, which leaves the original text on
screen.

## Rules of the road

- **Never touch code.** Fenced blocks and inline code spans are passed through
  verbatim. A swapped word inside a command is one the user would copy and run.
  Fence state is carried across flushes via a small file in `$TMPDIR/claude-phrase-swap/`,
  keyed by `messageId` and deleted on the final flush.
- **Stay fast.** This runs on the render path. No imports beyond the stdlib, no network,
  no filesystem walks.
- **Stay silent when nothing changed.** Emitting no output is the contract for
  "display the original" and is cheaper than echoing the delta back.

## Editing the word list

`phrases.json` ships the defaults. Personal, uncommitted additions go in
`~/.agent-skills/local-phrases.json` (same shape) — it overrides the shipped list,
and a `null` value turns a shipped phrase off:

```json
{
  "swaps": {
    "seam": "boundary",
    "delve": null
  }
}
```

This mirrors `~/.agent-skills/local-rules.json` for the PreToolUse engine.

Matching is case-insensitive, on word boundaries, and flexible across spaces and
hyphens — `load-bearing` also catches `load bearing`. Capitalization and apostrophe
style (straight vs curly) carry from the match to the replacement, so
`Load-bearing` becomes `Important`.

**Pick replacements that survive substitution.** The swap is dumb: it does not know
the grammar around the phrase. `honest take` → `take` reads fine anywhere; `let me be
honest` → `honestly` breaks on "let me be honest with you". If a phrase can't take a
drop-in replacement in every sentence, leave it out.

## Changing the hook

Run the tests, then `bash setup.sh` to deploy — never edit `~/.claude/hooks/` directly.

```bash
make test-message-display
bash setup.sh
```

Hooks load at session start, so a change only shows up in a **new** session.
