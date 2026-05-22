---
name: start-work
description: Create a git worktree for a ticket, run repo setup (conductor / superset / custom), and optionally launch your editor. Local counterpart to /super-work. Give it a Linear ID (e.g. LC-12345), pass a slug, or run with no args to be prompted.
argument-hint: "[LINEAR-ID | slug]"
---

# Start Work: Worktree + Setup for a Ticket

You are setting up a fresh git worktree for a work item so the user can start coding in isolation. Resolve the ticket, pick the source repo, create the worktree, run repo-specific setup, and optionally launch the editor.

This is the local-filesystem counterpart to `/super-work` (which creates Superset workspaces). Use this when the user wants a plain `git worktree` they can open in their own editor (VS Code, Cursor, Zed, …).

**Arguments:** $ARGUMENTS

**Pre-loaded context:**

- Ticket ID (from branch): !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- User branch prefix: !`~/.claude/skills/shared/scripts/context.sh user-slug`
- Repo remote: !`~/.claude/skills/shared/scripts/context.sh repo-remote`
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
- Config: !`cat ~/.claude/agent-skills.json 2>/dev/null || echo "needs-setup"`

**Setup check:** If `Config` shows `needs-setup`, stop: "Run `/setup-agent-skills` first to configure your work folder and branch prefix, then come back."

---

## Phase 0: Resolve the Work Item

Determine which ticket to start, in priority order:

1. **Argument** — if `$ARGUMENTS` matches `[A-Z]+-\d+` (Linear ID), use it directly.
2. **Session context** — if `/plan-work` produced a ticket + slug in this conversation, use them.
3. **Slug argument** — if `$ARGUMENTS` doesn't match the Linear pattern but looks like a slug (contains a hyphen, no spaces), use it as the slug and derive the ticket if it starts with one.
4. **Ask** — "What ticket are you starting? Give me a Linear ID (e.g. `LC-12345`)."

Once you have a Linear ID, fetch the issue:

```
mcp__claude_ai_Linear__get_issue { "issueId": "<TICKET>" }
```

**Derive the slug** (same rule as `/plan-work`):

- Pattern: `<lowercase-team>-<number>-<fragment>` — e.g. `lc-12345-loan-export`
- **Always produce a concise fragment.** Pick 2–4 keywords that capture the essence — not the literal title. Drop articles, prepositions, filler verbs ("add", "fix", "improve" unless they carry meaning), and detail meant for the ticket body. The fragment should read like a tag, not a sentence.
- **70-char hard cap on the full slug** (including `<team>-<num>-` prefix). The ticket prefix is never shortened — compress the fragment, not the ticket ID.
- Examples:
  - "Fix loan export when borrower has multiple co-applicants" → `lc-22054-loan-export-coapplicants`
  - "Make info icons smaller and gray on USDA and Residual Income screens" → `lc-21871-info-icon-styling`
  - "Improve UX of the deployment dashboard" → `lc-17331-deployments-ux`

The team prefix is everything before the first `-` of the ticket ID, lowercased (e.g. `LC-12345` → team `lc`). Use the **uppercase** team prefix (`LC`) as the config key for Linear-related lookups; use the lowercase form for filesystem things.

---

## Phase 1: Mark the Linear Ticket "In Progress"

Skip this phase entirely if no Linear ticket is involved (slug-only / free-text path). Otherwise, transition the ticket so teammates can see you've picked it up.

Read `~/.claude/skills/shared/references/linear-mark-in-progress.md` and follow it precisely. It covers state-check, per-team status resolution + caching to `linear_team_statuses.<TEAM>.in-progress` in `~/.claude/agent-skills.json`, and the API transition. On any Linear API failure, report and continue — don't block worktree setup.

---

## Phase 2: Resolve Source Repo (by team)

Read `team_repos` from `~/.claude/agent-skills.json` — a map of lowercase team prefix → absolute path to the source repo.

```json
{ "team_repos": { "lc": "/Volumes/Code/Repos/loancrate/loancrate" } }
```

- **Match found** → verify the path exists and is a git repo: `git -C <path> rev-parse --is-inside-work-tree`. If verification fails, warn and ask the user to re-enter the path (then re-save).
- **No match** → ask:

  > "I don't have a repo configured for team `<TEAM>`. What's the absolute path to its source repo?"

  Verify the answer is a git repo, then save:

  ```bash
  python3 -c "
  import json, os
  path = os.path.expanduser('~/.claude/agent-skills.json')
  d = json.load(open(path))
  d.setdefault('team_repos', {})['<team>'] = '<absolute-path>'
  json.dump(d, open(path, 'w'), indent=2)
  "
  ```

The resolved source repo is `<source-repo>`. From here on, run all `git` commands with `-C <source-repo>` unless otherwise noted.

---

## Phase 3: Compute Branch and Worktree Path

- **Branch name**: `<user-prefix>/<slug>` (lowercase throughout) — e.g. `ambrose/lc-12345-fix-loan-export`. Matches the convention used by `/plan-work` and `/super-work`.
- **Worktree path**: sibling of `<source-repo>`, named with the slug.
  - Source: `/Volumes/Code/Repos/loancrate/loancrate`
  - Worktree: `/Volumes/Code/Repos/loancrate/lc-12345-fix-loan-export`

Check existing state:

```bash
git -C <source-repo> worktree list --porcelain
git -C <source-repo> branch --list <branch>
```

Branching on what you find:

- **Worktree already exists at that path or for that branch** → ask: "Worktree already exists at `<existing-path>` for `<branch>`. Open editor there instead of recreating?" If yes, skip to Phase 7 (Launch Editor) with the existing path. If no, stop and let the user decide.
- **Branch exists locally but no worktree** → offer to attach: `git worktree add <path> <branch>`. Skip the `-b` and base-branch steps below.
- **Path exists on disk but isn't a git worktree** → stop and warn. Don't overwrite anything.
- **Clean state** → continue.

---

## Phase 4: Confirm Base Branch

Determine the default base:

```bash
git -C <source-repo> symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/origin/||'
```

Fall back to `main` if the symbolic ref isn't set.

Ask:

> "Branch `<branch>` will be created from `<base>`. OK, or branch from somewhere else?"

Fetch latest before branching:

```bash
git -C <source-repo> fetch origin <base>
```

---

## Phase 5: Create the Worktree

```bash
git -C <source-repo> worktree add -b <branch> <worktree-path> origin/<base>
```

If this fails (locked worktree, branch name conflict, dirty index, etc.), report the error verbatim and stop — don't attempt clever recovery without user input.

---

## Phase 6: Run Setup

Read `repo_setup` from `~/.claude/agent-skills.json` — a map of `<source-repo-absolute-path>` → setup command string. Placeholders supported inside the command:

- `{WORKTREE}` → absolute worktree path
- `{SOURCE}` → absolute source-repo path

**If configured** → expand placeholders and run from the worktree directory.

**If not configured**, auto-detect in this order (run each check against the worktree, not the source repo):

1. **Conductor** — `<worktree>/conductor_setup.sh` exists
   → command: `CONDUCTOR_ROOT_PATH={SOURCE} bash conductor_setup.sh`
2. **Superset** — `<worktree>/.superset/config.json` exists and has a `setup` array
   → join entries with `&&`; replace `$SUPERSET_ROOT_PATH` with `{SOURCE}`
3. **Generic** — `<worktree>/scripts/setup.sh` exists
   → command: `bash scripts/setup.sh`
4. **None match** → ask: "I didn't detect a setup script for this repo. What command should I run inside the worktree? (Or type `skip`.)" Use `{WORKTREE}` and `{SOURCE}` placeholders if relevant.

After detecting (or being given) a command, ask:

> "Detected setup command: `<command>`. Save this as the default for `<source-repo>`?"

If yes, save under `repo_setup.<source-repo-absolute-path>` in agent-skills.json.

**Run it.** Stream output to the user (don't background — they want to see the install). If it fails, report which step failed and stop. The worktree still exists; the user can investigate and re-run setup manually with the command you printed.

---

## Phase 7: Launch Editor

Read `editor_command` from `~/.claude/agent-skills.json`.

**If not set:**

- Ask: "What editor should I launch new worktrees in? (e.g. `code` for VS Code, `cursor`, `zed`, or `none` to skip.)"
- If they pick something other than `none`, verify the command resolves: `command -v <editor>`. If it doesn't, tell them and re-ask.
- Save to `editor_command` in agent-skills.json (use the string `none` to disable).

**If `none`** → print `cd <worktree-path>` and skip launch.

**Otherwise** → launch in background:

```bash
<editor> <worktree-path>
```

---

## Phase 8: Confirm

Report concisely:

- **Worktree:** `<worktree-path>`
- **Branch:** `<branch>` (from `origin/<base>`)
- **Setup:** succeeded / failed / skipped
- **Editor:** launched `<editor>` / skipped (with `cd` command)
- **Cleanup hint:** "When done, run `bash ~/.claude/skills/start-work/scripts/cleanup-worktree.sh <worktree-path>` to remove the worktree and branch. With no arg, you'll get an fzf picker of linked worktrees in the current repo."

Stop. Don't auto-start the dev server — that's the user's call (or handled by Conductor/Superset which have their own run scripts).

---

## Cleanup

Cleanup is deterministic — no AI needed. The companion script handles it:

```bash
bash ~/.claude/skills/start-work/scripts/cleanup-worktree.sh [<worktree-path-or-branch>] [--force]
```

With no target, it opens an fzf picker listing linked worktrees in the current repo (excluding the main worktree). It verifies the worktree is clean and the branch is merged (or has a merged PR) before removing. `--force` skips those checks.

---

## Guidelines

- **One worktree per ticket per repo.** If one already exists, offer to switch the editor to it rather than recreating.
- **Lowercase slugs.** Match `/plan-work` and `/super-work`. The branch name is `<prefix>/<slug>`, all lowercase.
- **Sibling-of-source path layout.** Predictable, visible, easy to clean up.
- **Don't touch the source repo's working tree.** Only `git worktree add` from it. Fetch is fine.
- **Don't auto-start dev servers.** Setup builds; the user (or their tooling) starts `pnpm dev` / equivalent.
- **Surface failures, don't paper over them.** If setup fails, leave the worktree in place and tell the user what command to re-run.
