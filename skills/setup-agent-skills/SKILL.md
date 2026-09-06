---
name: setup-agent-skills
description: First-time setup for agent-skills workflow. Configures where plans and reviews are stored and your personal branch prefix. Run this once per machine before using /plan-work, /do-work, or other workflow skills.
argument-hint: ""
---

# Agent Skills Setup

You are configuring agent-skills for this machine. This takes about a minute and only needs to be done once. The settings are saved to `~/.claude/agent-skills.json`.

**Pre-loaded context:**
- Git user name: !`git config user.name 2>/dev/null || echo "unknown"`
- Existing config: !`cat ~/.claude/agent-skills.json 2>/dev/null || echo "not found"`

---

## Step 1: Work Folder Location

The **work folder** is where plans, reviews, and working notes for all your tickets are stored — outside of any repo, so they survive branch deletion and work across multiple repos.

Ask the user where they'd like to store these files. Suggest `~/Work` as the default. If they're on a work machine with iCloud or a cloud-synced folder, suggest that as an alternative (e.g. `~/Library/Mobile Documents/com~apple~CloudDocs/Work`).

Use `AskUserQuestion` with these options:
- `~/Work` (Recommended) — simple local folder
- `~/Documents/Work` — inside Documents
- Other / type a custom path

After they answer, expand the path (resolve `~`) and show the full absolute path for confirmation.

---

## Step 2: Branch Prefix

The **branch prefix** is prepended to all branch names you create (e.g. `ambrose/eng-42-dark-mode`). Suggest the first word of their git user name (lowercased) from the pre-loaded context.

Ask:
- `<suggested-prefix>` (Recommended) — from your git config
- Other / type your preferred prefix

---

## Step 3: Discover Superset Device (Optional)

Try to look up the Superset device ID now so `/super-work` never has to ask:

```
mcp__superset__list_devices {}
```

- If it succeeds and returns exactly one device → note the `device_id`
- If multiple devices → ask which to use as the default
- If it fails or Superset isn't connected → skip silently, `/super-work` will handle it on first use

---

## Step 4: Anything to Leave Off This Machine? (Optional)

`setup.sh` installs everything by default. The `exclude` key in the config is a persistent opt-out: `setup.sh` never installs anything listed there, and on every run it removes anything listed that it installed earlier. This is the place to declare it, so a fresh machine never gets the excluded pieces even once.

Ask with `AskUserQuestion` (single-select; the tool adds its own "Other" entry for a free-text answer):
- `Nothing — install everything` (Recommended)
- `Skip the workflow skills` — plan-work, plan-review, do-work, do-fixes, code-review (for machines where an org repo already provides them)
- `Skip all hooks` — pretooluse, notification, message-display, window-title

If they pick "Other", they can name any mix of the items below. Map what they say onto this schema — every key is a list, and `"all"` in a list excludes everything under that key:

```json
"exclude": {
  "hooks":       ["pretooluse", "notification", "message-display", "window-title"],
  "mcp":         ["playwright"],
  "guidance":    ["core", "personal"],
  "skills":      ["<skill directory name>", "..."],
  "attribution": ["sessionUrl", "commit", "pr"],
  "cli":         ["claude-resume", "reclaude"]
}
```

`shared` cannot be excluded (other skills depend on it). Anything unknown is warned about and ignored by `setup.sh`, so a typo is harmless but worth catching here.

---

## Step 5: Write Config

Merge the confirmed values into `~/.claude/agent-skills.json`. Read the existing file first and only set the keys you collected — other skills store their own keys here (`team_repos`, `linear_team_statuses`, `projects`, …) and a re-run must not wipe them:

```bash
python3 -c "
import json, os
p = os.path.expanduser('~/.claude/agent-skills.json')
try:
    d = json.load(open(p))
except (FileNotFoundError, json.JSONDecodeError):
    d = {}
d['user_prefix'] = '<prefix>'
d['work_root'] = '<absolute-path>'
# Include device_id if discovered
# d['device_id'] = '<device-id>'
# Only when the user chose something in Step 4 — replace the lists they named,
# leave keys they did not mention alone:
# d.setdefault('exclude', {})['skills'] = ['plan-work', 'do-work']
with open(p, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
"
```

Create the work folder if it doesn't exist:
```bash
mkdir -p "<absolute-path>"
```

---

## Step 6: Confirm

Show a summary:
> "Setup complete.
>
> - **Work folder:** `<path>` ✓
> - **Branch prefix:** `<prefix>` ✓
> - **Superset device:** `<device-name>` ✓  (or "not connected — run `/super-work` to set up later")
> - **Excluded:** `skills: plan-work, do-work` (or "nothing — everything installs")
>
> Run `bash setup.sh` in the agent-skills repo to apply, then `/plan-work <LINEAR-ID>` to start your first work session. To change exclusions later, edit the `exclude` key in `~/.claude/agent-skills.json` (or run `setup.sh --without <component>`) and re-run `setup.sh`."

If there was a pre-existing config (shown in pre-loaded context), note what changed.
