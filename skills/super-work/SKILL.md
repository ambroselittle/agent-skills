---
name: super-work
description: Open a Superset workspace for a work item. Discovers context from the current session, branch, or a given Linear ID — creates the workspace on the right repo/branch. Run this when you're ready to start coding in Superset.
argument-hint: "[LINEAR-ID | slug]"
---

# Super Work: Launch a Superset Workspace

You are creating a Superset workspace for a work item. Your job is to figure out what to work on, set up the workspace on the right repo and branch, and hand off to the user to open it in the Superset desktop app.

**Arguments:** Use the arguments supplied with this skill invocation or the user's current request.

Read `~/.agent-skills/skills/shared/references/harness-capabilities.md` before proceeding. Use its active-harness mappings for skills, questions, progress, delegation, model tiers, project instructions, and connected tools.

**Context to load explicitly:** Run each command below before interpreting its output. These are shell commands to execute, not values supplied automatically by the harness.

- Ticket ID (from branch): `bash ~/.agent-skills/scripts/shared/context.sh ticket-id`
- Work folder (from branch): `bash ~/.agent-skills/scripts/shared/context.sh work-folder`
- User branch prefix: `bash ~/.agent-skills/scripts/shared/context.sh user-slug`
- Repo remote: `bash ~/.agent-skills/scripts/shared/context.sh repo-remote`
- Effective config: `bash ~/.agent-skills/scripts/shared/context.sh config`
- Superset CLI: verify `superset` is available, then run `superset hosts list --json`; a successful authenticated response means `ready`. Missing executable means `not-installed`; an authentication failure means `needs-login`. Report other failures using the fallback rules below.

**Setup checks (in order):**

1. If `Work folder` shows `needs-setup`, stop: "Run `/setup-agent-skills` first to configure your work folder, then come back."

2. If `Superset CLI` shows `not-installed`, stop: "The Superset CLI isn't installed. Install it with:

   ```
   brew tap superset-sh/tap
   brew install superset-sh/tap/superset
   ```

   Then re-run `/super-work`."

3. If `Superset CLI` shows `needs-login`, stop: "Superset CLI is installed but not authenticated. Run `superset auth login` (or set `SUPERSET_API_KEY`), then re-run `/super-work`."

---

## Phase 0: Resolve the Work Item

Determine which plan to open a workspace for, in priority order:

1. **Session context** — if `/plan-work` was just run in this conversation, the ticket and slug are already known. Use them.
2. **Argument** — if the invocation input matches `[A-Z]+-\d+` (Linear ID) or looks like a slug, use it. For a Linear ID, look for a matching work folder under the configured `work_root`.
3. **Branch context** — use loaded `Ticket ID` and `Work folder` if not "none".
4. **Ask** — "What are you working on? Give me a Linear ID or slug."

Once resolved, derive the slug:

- If a plan exists at `<work-folder>/plan.md`, read the `branch` from its frontmatter for the slug.
- Otherwise derive the slug from the ticket: fetch the Linear issue title with the available connected Linear tool and apply the same slug rule as `/plan-work` — concise 2–4 keyword fragment that reads like a tag (drop articles, prepositions, filler verbs); pattern is `<lowercase-team>-<number>-<fragment>`; 70-char hard cap on the full slug. The ticket prefix is never shortened.
- If argument is already a slug (no `[A-Z]+-\d+` pattern), use it directly.

---

## Phase 1: Mark the Linear Ticket "In Progress"

Skip this phase entirely if no Linear ticket is involved (slug-only / plan-only path). Otherwise, transition the ticket so teammates can see you've picked it up.

Read `~/.agent-skills/skills/shared/references/linear-mark-in-progress.md` and follow it precisely. It covers state-check, per-team status resolution + caching to `linear_team_statuses.<TEAM>.in-progress` in `~/.agent-skills/config.json`, and the API transition. On any Linear API failure, report and continue — don't block workspace creation.

---

## Phase 2: Identify Target Repo

If a plan exists, scan its phases for `**Repo:**` annotations:

- **No annotations** → single-repo plan; use the current `Repo remote` from loaded context.
- **One unique repo** → use it directly.
- **Multiple repos** → ask: "This plan has work across: [list]. Which repo do you want to open first?" Run `/super-work` again for the others.

If no plan exists, use the current `Repo remote` from loaded context (or the repo associated with the resolved ticket).

The selected repo is `<target-repo>`.

---

## Phase 3: Resolve Host and Project IDs

All Superset calls run through the `superset` CLI. Request `--json` explicitly for machine-readable calls regardless of active harness.

### Host ID

Read `host_id` from the effective configuration loaded above. (Older configs may have `device_id` — ignore it and create a fresh `host_id`.)

If not present:

```bash
superset hosts list --json
```

- One host → use it automatically
- Multiple → ask which to use (match on name)

Save `host_id` with the shared config command, encoding the value as a JSON string:

```bash
bash ~/.agent-skills/scripts/shared/context.sh config-set host_id '"<host-id>"'
```

### Project ID

Read the `projects` map from the effective configuration — keyed by repo remote (e.g. `loancrate/web`).

If `<target-repo>` is not in the map:

```bash
superset projects list --json
```

Match by name or path against `<target-repo>` (parse JSON with `jq`). If ambiguous, ask the user to pick.

Save to config:

```bash
bash ~/.agent-skills/scripts/shared/context.sh config-set projects '<target-repo>' '"<project-id>"'
```

Encode the ID as JSON and quote the repo key safely; preserve unrelated projects.

---

## Phase 4: Check for Existing Workspace

```bash
superset workspaces list --host "<host-id>" --json
```

Parse the JSON and look for a workspace whose name matches the slug (or contains the ticket token).

If one exists:

> "A workspace `<name>` already exists for this ticket. Open it in Superset instead of creating a new one."

Stop here — the user opens the existing workspace from the Superset desktop app.

Otherwise, continue to Phase 5.

---

## Phase 5: Confirm Base Branch

Ask the user which branch to base the workspace on:

> "Branch `<user-prefix>/<slug>` will be created from `main`. OK, or branch from somewhere else?"

- **main / OK** → use `main`
- **Other** → ask for the branch name to use as base

The confirmed base is `<base-branch>`.

---

## Phase 6: Create Workspace

```bash
superset workspaces create \
  --host "<host-id>" \
  --project "<project-id>" \
  --name "<slug>" \
  --branch "<user-prefix>/<slug>" \
  --base-branch "<base-branch>" \
  --json
```

Capture the returned workspace ID from the JSON output. If creation fails (non-zero exit), report the error verbatim and stop.

Confirm: "Workspace `<slug>` created — open it in the Superset desktop app to start working."

If the plan has multiple repos with remaining work:

> "When you're ready for the next repo (`<next-repo>`), run `/super-work` again."

---

## Fallback: CLI errors

If any `superset` call exits non-zero, surface the error message and the suggested fix:

- `Not logged in` → "Run `superset auth login` (or set `SUPERSET_API_KEY`) and re-run `/super-work`."
- Connection / network errors → "Couldn't reach Superset. Check `superset status` and your network, then re-run `/super-work`."
- Anything else → report the full error and stop. Don't retry or guess.

---

## Guidelines

- **A plan is helpful but not required.** A Linear ticket ID alone is enough — slug is derived from the issue title.
- **One workspace per repo.** For multi-repo work, open them sequentially — run `/super-work` again for each additional repo.
- **Host and project IDs are cached.** Look them up once, save them, skip the lookup next time.
- **The work folder lives outside the repo** — it's accessible from any worktree. No copying needed.
- **Don't auto-start agents.** Create the workspace and hand off. The user opens it in the Superset desktop app and drives from there.
