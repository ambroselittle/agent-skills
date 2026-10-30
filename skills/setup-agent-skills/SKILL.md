---
name: setup-agent-skills
description: First-time setup for agent-skills workflow. Configures where plans and reviews are stored and your personal branch prefix. Run this once per machine before using /plan-work, /do-work, or other workflow skills.
argument-hint: ""
---

# Agent Skills Setup

Use the active agent’s native question, progress, skill invocation, and delegation capabilities as described in [harness capabilities](../shared/references/harness-capabilities.md). Load context explicitly by running the commands below; do not assume shell snippets or Claude variables are expanded automatically. Read shared preferences from `~/.agent-skills/config.json`; agent-specific overrides live under `agents.<agent>`.

You are configuring agent-skills for this machine. The settings are saved to `~/.agent-skills/config.json`.

Load the current git user and effective shared configuration explicitly:

```bash
git config user.name
```

```bash
~/.agent-skills/scripts/shared/context.sh config
```

The installer imports legacy Claude preferences automatically, retains the original files, and applies versioned migrations. Codex-specific overrides live under `agents.codex`. Set common preferences at the top level unless the user asks for an agent-specific difference. Reapplying setup detects installed supported agents; no target flag is required. Use `--target claude|codex|both` only for an explicit override.

---

## Step 1: Work Folder Location

The **work folder** is where plans, reviews, and working notes for all your tickets are stored — outside of any repo, so they survive branch deletion and work across multiple repos.

Ask the user where they'd like to store these files. Suggest `~/Work` as the default. If they're on a work machine with iCloud or a cloud-synced folder, suggest that as an alternative (e.g. `~/Library/Mobile Documents/com~apple~CloudDocs/Work`).

Ask through the available question interface, or conversationally when none is available:
- `~/Work` (Recommended) — simple local folder
- `~/Documents/Work` — inside Documents
- A custom path supplied by the user

After they answer, expand the path (resolve `~`) and show the full absolute path for confirmation.

---

## Step 2: Branch Prefix

The **branch prefix** is prepended to all branch names you create (e.g. `ambrose/eng-42-dark-mode`). Suggest the first word of their git user name (lowercased) from the loaded context.

Ask:
- `<suggested-prefix>` (Recommended) — from your git config
- A different prefix supplied by the user

---

## Step 3: Discover Superset Host (Optional)

If the Superset CLI is available and authenticated, discover a default host for `/super-work`:

```bash
superset hosts list --json
```

- Exactly one host → note its `host_id` when consistent with the user’s authorized computer and execution preferences; otherwise ask before selecting it.
- Multiple hosts → ask which to use as the default.
- Zero hosts → leave `host_id` unset and explain that a host must be connected in Superset before `/super-work` can create a workspace.
- Missing CLI, authentication, or connection → skip this optional discovery; `/super-work` will handle setup on first use.

An old `device_id` is not a host identifier. Preserve unrelated configuration, but do not reuse that value or select a remote computer without authorization.

---

## Step 4: Anything to Leave Off This Machine? (Optional)

`setup.sh` installs everything by default. The `exclude` key in the config is a persistent opt-out: `setup.sh` never installs anything listed there, and on every run it removes anything listed that it installed earlier. This is the place to declare it, so a fresh machine never gets the excluded pieces even once.

Ask a single-choice question through the available interface; allow a free-text answer:
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

Save the confirmed values in `~/.agent-skills/config.json`. Read the existing file first and only set the keys you collected — other skills store their own keys here (`team_repos`, `linear_team_statuses`, `projects`, …) and a re-run must not wipe them:

Use the shared config writer for each confirmed value. Its final argument is a JSON value; quote strings correctly and set only collected keys. For example:

```bash
~/.agent-skills/scripts/shared/context.sh config-set --shared user_prefix '"ambrose"'
```

```bash
~/.agent-skills/scripts/shared/context.sh config-set --shared work_root '"/Users/ambrose/Work"'
```

Substitute the actual confirmed values. Set optional `host_id` and only the named `exclude` categories the same way, passing each nested key separately. Use `--shared` for common defaults; use `agents codex` or `agents claude` key components only for an explicitly requested per-agent preference. Leave every other key intact. Read `config` again to verify the saved effective values.

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
> - **Host:** `<host-name>` ✓  (or "not configured — run `/super-work` to set up later")
> - **Excluded:** `skills: plan-work, do-work` (or "nothing — everything installs")
>
> Run `bash setup.sh` in the agent-skills repo to apply, then `/plan-work <LINEAR-ID>` to start your first work session. To change exclusions later, edit the `exclude` key in `~/.agent-skills/config.json` (or run `setup.sh --without <component>`) and re-run `setup.sh`."

If there was a pre-existing config (shown in loaded context), note what changed.
