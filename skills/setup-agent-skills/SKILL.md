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

## Step 4: Write Config

Write `~/.claude/agent-skills.json` with all confirmed values:

```bash
python3 -c "
import json, os
d = {
  'user_prefix': '<prefix>',
  'work_root': '<absolute-path>',
}
# Include device_id if discovered
# d['device_id'] = '<device-id>'
json.dump(d, open(os.path.expanduser('~/.claude/agent-skills.json'), 'w'), indent=2)
"
```

Create the work folder if it doesn't exist:
```bash
mkdir -p "<absolute-path>"
```

---

## Step 5: Confirm

Show a summary:
> "Setup complete.
>
> - **Work folder:** `<path>` ✓
> - **Branch prefix:** `<prefix>` ✓
> - **Superset device:** `<device-name>` ✓  (or "not connected — run `/super-work` to set up later")
>
> Run `/plan-work <LINEAR-ID>` to start your first work session."

If there was a pre-existing config (shown in pre-loaded context), note what changed.
