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

Labels are self-bootstrapping — first `/wtf` invocation creates the `WTF` and `In Progress` labels on the repo if they don't exist.

## Installing the worker

The worker runs on a launchd schedule (every 2 hours, 9am–11pm local). Install it:

```bash
bash setup.sh --install-wtf-worker           # install and load
bash setup.sh --install-wtf-worker --test    # install, then fire an immediate smoke test
bash setup.sh --uninstall-wtf-worker         # unload and remove
```

Both commands are idempotent. Re-running install is a clean reload; uninstall is a no-op when nothing's installed.

### What the installer does

- Renders `templates/wtf-worker.plist.template` → `~/Library/LaunchAgents/com.ambroselittle.wtf-worker.plist` (with `{{REPO_ROOT}}` and `{{HOME}}` substituted).
- Snapshots your `~/.gitconfig` to `~/.agent-skills/wtf-worker.gitconfig`. Necessary because launchd's sandbox can't read iCloud-synced paths, and a common pattern is to symlink dotfiles into iCloud. The plist points `GIT_CONFIG_GLOBAL` at the snapshot.
- Loads the job with `launchctl load`.

### Monitoring

| Command | What it shows |
|---|---|
| `launchctl list \| grep wtf-worker` | PID (or `-`), last exit code, label. If the label isn't there, the job isn't loaded. |
| `tail -f ~/Library/Logs/wtf-worker.log` | The worker's own timestamped log — what it's doing, what it found, what it's claiming |
| `tail -f ~/Library/Logs/wtf-worker.out.log` | Raw stdout from launchd invocations |
| `tail -f ~/Library/Logs/wtf-worker.err.log` | Raw stderr from launchd invocations (git/gh/claude) |
| `launchctl start com.ambroselittle.wtf-worker` | Manual fire — runs immediately without waiting for the next scheduled tick |
| `scripts/wtf-worker.sh --dry-run` | From the repo root: find work and print the planned action without claiming, cloning, or invoking claude |

### Repo clones

The worker uses **HTTPS over `gh` credential helper** for its `/tmp/` clones — not SSH — because launchd's sandbox can't reach the 1Password SSH agent socket on this user's machine. This applies only to the disposable worker clones; no real repo's `origin` is affected.
