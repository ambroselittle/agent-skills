---
name: super-work
description: Open a Superset workspace for a planned work item and launch /do-work inside it. Reads the plan from your work folder, resolves the right repo and project, creates the workspace, and fires up the agent. Run after /plan-work when you're ready to start coding.
argument-hint: "[LINEAR-ID | slug]"
---

# Super Work: Plan → Superset Workspace → Do Work

You are opening a Superset workspace for a work item that has already been planned and is ready to implement.

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

Once resolved, read the plan at `<work-folder>/plan.md`. If no plan exists: "No plan found. Run `/plan-work <ticket>` first."

---

## Phase 1: Identify Repos

Scan the plan's phases for `**Repo:**` annotations and collect the unique set.

- **No annotations** (single-repo plan) → one repo: use the current `Repo remote` from pre-loaded context, or the plan's source context if available.
- **One unique repo** → use it directly.
- **Multiple repos** → ask: "This plan has work across: [list]. Which repo do you want to open first?" Wait for selection. You'll run `/super-work` again for the others when ready.

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

## Phase 4: Create the Workspace

```
mcp__superset__create_workspace {
  "deviceId": "<device-id>",
  "projectId": "<project-id>",
  "workspaces": [{
    "name": "<slug>",
    "branchName": "<user-prefix>/<slug>",
    "baseBranch": "main"
  }]
}
```

Capture the returned workspace ID. If creation fails, report the error and stop.

Switch to the new workspace:
```
mcp__superset__switch_workspace {
  "deviceId": "<device-id>",
  "workspaceId": "<workspace-id>"
}
```

---

## Phase 5: Launch Do-Work

```
mcp__superset__start_agent_session_with_prompt {
  "deviceId": "<device-id>",
  "workspaceId": "<workspace-id>",
  "prompt": "/do-work"
}
```

Confirm: "Workspace `<slug>` is open and `/do-work` is running inside it. Switch to it in Superset to watch or take over."

If the plan has remaining repos (multi-repo plan, more phases in other repos):
> "When you're ready for the next repo (`<next-repo>`), run `/super-work` again."

---

## Fallback: Superset Unavailable

If any Superset call fails with an auth or connection error:

1. Report what happened
2. Create the branch locally: `git checkout -b <user-prefix>/<slug>`
3. Tell the user: "Created branch locally. Re-authenticate Superset (`claude mcp auth superset`) for automatic workspace creation next time. Run `/do-work` manually when ready."

---

## Guidelines

- **Plan must exist before running this.** `/super-work` is a launcher, not a planner. If there's no plan, direct to `/plan-work`.
- **One workspace per repo.** For multi-repo plans, open them sequentially — don't batch-create.
- **Device and project IDs are cached.** Look them up once, save them, skip the lookup next time.
- **The work folder is already accessible from any worktree** — it lives outside the repo. No copying needed.
