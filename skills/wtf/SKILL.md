---
name: wtf
description: Capture a mid-session correction for the autonomous worker to act on later. Writes a local file and appends to a rolling GitHub backlog issue in the background so you stay in flow.
argument-hint: "<what went wrong>"
---

# /wtf — Capture a correction

When the user catches you doing something wrong, they type `/wtf <what went wrong>`. This skill persists the correction so an autonomous worker can classify and fix it later. The skill returns in <1s; the GitHub backlog update happens in the background.

**Arguments:** `$ARGUMENTS` — free-form description of what went wrong. The user's raw reaction is good; no need to sanitize.

## Step 1: Capture locally (synchronous)

Run the capture script, passing the user's message verbatim. Capture the file path it prints:

```bash
CAPTURE_FILE=$(~/.claude/skills/wtf/scripts/capture.sh "$ARGUMENTS")
```

This writes `~/.agent-skills/wtf/<timestamp>-<slug>.md` with frontmatter (session, cwd, branch), the user's verbatim message, and the last ~10 turns extracted from the transcript. Runs in well under a second.

## Step 2: Queue the backlog append (asynchronous, non-blocking)

Fire off the GitHub backlog append in the background so the skill returns immediately:

```bash
nohup ~/.claude/skills/wtf/scripts/backlog-append.sh "$CAPTURE_FILE" \
  > ~/Library/Logs/wtf-backlog-append.log 2>&1 &
disown
```

The background script looks for an open `WTF`-labeled issue in `ambroselittle/agent-skills` that isn't currently `In Progress`, appends this correction to its body, or creates a new issue if none is open. `disown` ensures it survives the skill returning.

## Step 3: Report back

Tell the user:

- **Captured to:** `$CAPTURE_FILE`
- **Backlog update:** running in background — check `~/Library/Logs/wtf-backlog-append.log` if anything seems off

Be brief. The user was in the middle of something and just wants to confirm the capture landed. Do not summarize the correction back to them.

## Notes

- **Background append vs Agent spawn.** The plan originally specified spawning an `Agent` for the GH work. In implementation, the operations are fully deterministic (list → view → edit, or create), so a shell script fits `skill-authoring.md`'s "deterministic work should be scripts, not AI" guidance — faster, no LLM cost, and the fire-and-forget behavior is identical.
- **Labels are self-bootstrapping.** `backlog-append.sh` idempotently ensures the `WTF` and `In Progress` labels exist on every run, so the skill works standalone even before the worker is installed via `setup.sh --install-wtf-worker`.
