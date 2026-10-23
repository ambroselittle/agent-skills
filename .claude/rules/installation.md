## Installation via setup.sh Only

Never directly edit, copy, or overwrite files in installed locations:
- `~/.claude/hooks/`
- `~/.claude/skills/` and `~/.agents/skills/`
- `~/.agent-skills/{skills,scripts,source}` links
- Codex hook adapters under `${CODEX_HOME:-~/.codex}/hooks/`
- Managed blocks in user-level `CLAUDE.md` and `AGENTS.md`
- `~/.claude/settings.json` (hook/permission entries)
- Any other integration that `setup.sh` manages

Always make changes in the source repo (this repo), then run:
```bash
bash setup.sh
```

to deploy to detected installed agents; use `--target` only for an explicit override. Use `~/.agent-skills/config.json` for shared preferences and `agents.<agent>` for overrides. Personal text outside protected guidance blocks remains user-owned. Direct edits to installed files will be overwritten on the next setup run and create divergence between source and installed state that is hard to track.

This also applies to workarounds: if a hook or permission is blocking an action, fix the rule in the source and deploy via setup.sh — do not bypass by editing the installed copy.
