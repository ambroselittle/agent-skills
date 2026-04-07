## Installation via setup.sh Only

Never directly edit, copy, or overwrite files in installed locations:
- `~/.claude/hooks/`
- `~/.claude/skills/`
- `~/.claude/settings.json` (hook/permission entries)
- Any other path that `setup.sh` manages

Always make changes in the source repo (this repo), then run:
```bash
bash setup.sh
```

to deploy. Direct edits to installed files will be overwritten on the next setup run and create divergence between source and installed state that is hard to track.

This also applies to workarounds: if a hook or permission is blocking an action, fix the rule in the source and deploy via setup.sh — do not bypass by editing the installed copy.
