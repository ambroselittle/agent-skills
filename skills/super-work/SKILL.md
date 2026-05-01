---
name: super-work
description: Open a Superset workspace for a work item. Discovers context from the current session, branch, or a given Linear ID — creates the workspace on the right repo/branch and switches to it. Run this when you're ready to start coding in Superset.
argument-hint: "[LINEAR-ID | slug]"
---

# Super Work: Launch a Superset Workspace

You are creating and switching to a Superset workspace for a work item. Your job is to figure out what to work on, set up the workspace on the right repo and branch, and hand off to the user inside Superset.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Ticket ID (from branch): !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- Work folder (from branch): !`~/.claude/skills/shared/scripts/context.sh work-folder`
- User branch prefix: !`~/.claude/skills/shared/scripts/context.sh user-slug`
- Repo remote: !`~/.claude/skills/shared/scripts/context.sh repo-remote`

**Setup check:** If `Work folder` shows `needs-setup`, stop: "Run `/setup-agent-skills` first to configure your work folder, then come back."

---

## Phase 0: Resolve the Work Item

Determine which plan to open a workspace for, in priority order:

1. **Session context** — if `/plan-work` was just run in this conversation, the ticket and slug are already known. Use them.
2. **Argument** — if `$ARGUMENTS` matches `[A-Z]+-\d+` (Linear ID) or looks like a slug, use it. For a Linear ID, look for a matching work folder under the configured `work_root`.
3. **Branch context** — use pre-loaded `Ticket ID` and `Work folder` if not "none".
4. **Ask** — "What are you working on? Give me a Linear ID or slug."

Once resolved, derive the slug:
- If a plan exists at `<work-folder>/plan.md`, read the `branch` from its frontmatter for the slug.
- Otherwise derive the slug from the ticket: fetch the Linear issue title with `mcp__claude_ai_Linear__get_issue` and apply the same slug rules as `/plan-work` (lowercase team + number + title fragment, 72-char max).
- If argument is already a slug (no `[A-Z]+-\d+` pattern), use it directly.

---

## Phase 1: Identify Target Repo

If a plan exists, scan its phases for `**Repo:**` annotations:

- **No annotations** → single-repo plan; use the current `Repo remote` from pre-loaded context.
- **One unique repo** → use it directly.
- **Multiple repos** → ask: "This plan has work across: [list]. Which repo do you want to open first?" Run `/super-work` again for the others.

If no plan exists, use the current `Repo remote` from pre-loaded context (or the repo associated with the resolved ticket).

The selected repo is `<target-repo>`.

---

## Phase 2: Resolve Device and Project IDs

### Device ID

Read `device_id` from `~/.claude/agent-skills.json`.

If not present:
```
mcp__superset__list_devices {}
```
- One device → use it automatically
- Multiple → ask which to use

Save `device_id` to `~/.claude/agent-skills.json`:
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/agent-skills.json')
d = json.load(open(path))
d['device_id'] = '<device-id>'
json.dump(d, open(path, 'w'), indent=2)
"
```

### Project ID

Read `projects` map from `~/.claude/agent-skills.json` — keyed by repo remote (e.g. `loancrate/web`).

If `<target-repo>` is not in the map:
```
mcp__superset__list_projects { "deviceId": "<device-id>" }
```
Match by name or path against `<target-repo>`. If ambiguous, ask the user to pick.

Save to config:
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/agent-skills.json')
d = json.load(open(path))
d.setdefault('projects', {})['<target-repo>'] = '<project-id>'
json.dump(d, open(path, 'w'), indent=2)
"
```

---

## Phase 3: Check for Existing Workspace

```
mcp__superset__list_workspaces { "deviceId": "<device-id>" }
```

If a workspace already exists whose name matches the slug (or contains the ticket token):

> "A workspace `<name>` already exists for this ticket. Switch to it instead of creating a new one?"

- **Yes** → use `mcp__superset__switch_workspace` and skip to Phase 5
- **No** → continue

---

## Phase 4: Confirm Base Branch

Ask the user which branch to base the workspace on:

> "Branch `<user-prefix>/<slug>` will be created from `main`. OK, or branch from somewhere else?"

- **main / OK** → use `main`
- **Other** → ask for the branch name to use as base

The confirmed base is `<base-branch>`.

---

## Phase 5: Create and Switch Workspace

```
mcp__superset__create_workspace {
  "deviceId": "<device-id>",
  "projectId": "<project-id>",
  "workspaces": [{
    "name": "<slug>",
    "branchName": "<user-prefix>/<slug>",
    "baseBranch": "<base-branch>"
  }]
}
```

Capture the returned workspace ID. If creation fails, report the error and stop.

```
mcp__superset__switch_workspace {
  "deviceId": "<device-id>",
  "workspaceId": "<workspace-id>"
}
```

Confirm: "Workspace `<slug>` is open — switch to it in Superset to start working."

If the plan has multiple repos with remaining work:
> "When you're ready for the next repo (`<next-repo>`), run `/super-work` again."

---

## Fallback: Superset Unavailable

If any Superset call fails with an auth or connection error:

1. Report what happened
2. Tell the user: "Re-authenticate Superset (`claude mcp auth superset`) and run `/super-work` again."

---

## Guidelines

- **A plan is helpful but not required.** A Linear ticket ID alone is enough — slug is derived from the issue title.
- **One workspace per repo.** For multi-repo work, open them sequentially — run `/super-work` again for each additional repo.
- **Device and project IDs are cached.** Look them up once, save them, skip the lookup next time.
- **The work folder lives outside the repo** — it's accessible from any worktree. No copying needed.
- **Don't auto-start agents.** Create the workspace and switch to it. The user drives from there.
