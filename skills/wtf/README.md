# /wtf — correction capture

Mid-session capture skill for the WTF feedback loop. When you catch Claude doing something wrong, type:

```
/wtf <what went wrong>
```

The skill returns almost immediately:

1. Writes a correction file to `~/.agent-skills/wtf/<timestamp>-<slug>.md` with frontmatter (session, cwd, branch), your verbatim message, and the last ~10 turns pulled from the session transcript.
2. Fires `backlog-append.sh` in the background — it finds an open `WTF`-labeled issue in `ambroselittle/agent-skills` that isn't currently `In Progress` and appends your correction to its body, or creates a new issue if none is open.

## Files

| File | Role |
|---|---|
| `SKILL.md` | Orchestration prose read by Claude on `/wtf` invocation |
| `scripts/capture.sh` | Writes the local correction file, prints its path |
| `scripts/extract-turns.sh` | Reads transcript JSONL; emits last ~10 turns as markdown |
| `scripts/backlog-append.sh` | Find-or-create the backlog issue; append the correction |

## Where this fits

The autonomous worker (see `scripts/wtf-worker.sh` once phase 2 lands) wakes up on a launchd schedule, drains the backlog, classifies each correction (behavioral guidance / rule / skill / hook / CLAUDE.md / upstream issue / no-action), and opens PRs against this repo. You review, request changes if needed, and the worker iterates on the next wake.

Install the worker once phase 3 lands:

```bash
bash setup.sh --install-wtf-worker
```

Labels are self-bootstrapping — first `/wtf` invocation creates the `WTF` and `In Progress` labels on the repo if they don't exist.
