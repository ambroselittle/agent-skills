---
name: wtf
description: Capture a mid-session correction for the autonomous worker to act on later. Writes a local file and appends to a rolling GitHub backlog issue in the background so you stay in flow.
argument-hint: "<what went wrong>"
---

# /wtf — Capture a correction

Use the active agent’s native question, progress, skill invocation, and delegation capabilities as described in [harness capabilities](../shared/references/harness-capabilities.md). Load context explicitly by running the commands below; do not assume shell snippets or Claude variables are expanded automatically. Read shared preferences from `~/.agent-skills/config.json`; agent-specific overrides live under `agents.<agent>`.

When the user catches you doing something wrong, they type `/wtf <what went wrong>`. This skill persists the correction so an autonomous worker can classify and fix it later. The skill returns in <1s; the GitHub backlog update happens in the background.

## Repo override (check first)

Before doing anything else, check whether the current repo provides its own `/wtf` skill. Resolve the repository root with `git rev-parse --show-toplevel` (works in regular checkouts and worktrees). Look for a repo-local override in `.agents/skills/wtf/SKILL.md`, then `.claude/skills/wtf/SKILL.md`; read the active agent’s applicable override when both exist. If an override exists:

1. Read that file.
2. Follow its instructions instead of the rest of this skill, passing the user’s message verbatim.
3. Stop — do not fall through to the default behavior below.

This lets repos route WTF captures to team- or project-specific destinations (different backlog repo, different sanitization rules, etc.). When no repo-local skill is present, continue with the default behavior.

**Input:** the user’s verbatim correction — free-form description of what went wrong. The user's raw reaction is good; no need to sanitize.

## Step 1: Capture locally (synchronous)

Run the capture script, passing the user's message verbatim. Capture the file path it prints:

```bash
AGENT_SKILLS_HARNESS=codex ~/.agent-skills/scripts/wtf/capture.sh "<verbatim correction>"
```

Set `AGENT_SKILLS_HARNESS` to the active agent (`claude` or `codex`) and replace the example message with the user’s actual correction. Save the returned path as `CAPTURE_FILE` for the next step.

This writes `~/.agent-skills/wtf/<timestamp>-<slug>.md` with frontmatter (agent, session when available, cwd, branch), the user's verbatim message, and the last ~10 turns when a supported transcript export is available. Claude transcript extraction uses its session adapter; Codex currently records a truthful transcript-unavailable note rather than reading a Claude transcript. Runs in well under a second.

## Step 2: Queue the backlog append (asynchronous, non-blocking)

Fire off the GitHub backlog append in the background so the skill returns immediately:

```bash
mkdir -p ~/.agent-skills/logs
( nohup ~/.agent-skills/scripts/wtf/backlog-append.sh "$CAPTURE_FILE" \
  > ~/.agent-skills/logs/wtf-backlog-append.log 2>&1 & )
```

The subshell-with-background pattern `( ... & )` detaches the process cleanly in both `bash` and `zsh` — no `disown` needed (which triggers a "no current job" warning on zsh). The background script looks for an open `WTF`-labeled issue in `ambroselittle/agent-skills` that isn't currently `In Progress`, appends this correction to its body, or creates a new issue if none is open.

## Step 3: Report back

Tell the user:

- **Captured to:** `$CAPTURE_FILE`
- **Backlog update:** running in background — check `~/.agent-skills/logs/wtf-backlog-append.log` if anything seems off

Be brief. The user was in the middle of something and just wants to confirm the capture landed. Do not summarize the correction back to them.

## Notes

- **Background append vs Agent spawn.** The plan originally specified spawning an `Agent` for the GH work. In implementation, the operations are fully deterministic (list → view → edit, or create), so a shell script fits `skill-authoring.md`'s "deterministic work should be scripts, not AI" guidance — faster, no LLM cost, and the fire-and-forget behavior is identical.
- **Labels are self-bootstrapping.** `backlog-append.sh` idempotently ensures the `WTF` and `In Progress` labels exist on every run, so the skill works standalone even before the worker is installed via `setup.sh --install-wtf-worker`.
