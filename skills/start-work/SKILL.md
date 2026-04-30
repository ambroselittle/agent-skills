---
name: start-work
description: Kick off a new work session from a Linear ticket. Fetches the issue, generates a slug, creates a Superset workspace (branch + worktree) named after it, and optionally launches /plan-work inside it automatically.
argument-hint: "[LINEAR-ID]"
---

# Start Work: Linear Ticket → Superset Workspace

You are setting up a new work session from a Linear issue. Your job is to fetch the ticket, generate a consistent slug, create a named Superset workspace with the right branch, and hand off to `/plan-work` inside it.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Ticket ID (from current branch, if any): !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- User branch prefix: !`~/.claude/skills/shared/scripts/context.sh user-slug`
- Repo remote (owner/repo): !`~/.claude/skills/shared/scripts/context.sh repo-remote`

---

## Phase 0: Resolve the Ticket

Determine the Linear issue ID:

- `$ARGUMENTS` matches `[A-Z]+-\d+` → use it directly
- `$ARGUMENTS` empty and pre-loaded `Ticket ID` is not "none" → use that
- Otherwise: "Provide a Linear issue ID (e.g. `ENG-42`) to start."

Fetch the issue:
```
mcp__claude_ai_Linear__get_issue { "issueId": "<ID>" }
```

Summarize the issue title and description in 1–2 sentences.

---

## Phase 1: Generate and Confirm the Slug

Apply the standard slug rules:

- Pattern: `<lowercase-team>-<number>-<title-fragment>` — e.g. `eng-42-dark-mode-settings`
- **72-char max.** If a naive kebab-case of the title would exceed it, reformulate a concise but meaningful summary — do not blindly truncate. The `<team>-<number>-` prefix is never shortened.
- This slug is used for: the Superset workspace name, the branch name suffix, and the future the work folder directory.

**Branch name:** `<user-prefix>/<slug>` — e.g. `ambrose/eng-42-dark-mode-settings`

Show the user what you're about to create:

> "Creating workspace **`eng-42-dark-mode-settings`** on branch **`ambrose/eng-42-dark-mode-settings`**. Sound right?"

Wait for confirmation or a correction before proceeding. A wrong workspace name is annoying to fix.

---

## Phase 2: Resolve Device and Project

### Find the device

```
mcp__superset__list_devices {}
```

- If exactly one device → use it, no need to ask
- If multiple → ask: "Which device should I create the workspace on?" and list names

### Find the project

```
mcp__superset__list_projects { "deviceId": "<deviceId>" }
```

Match the project to the current repo using the pre-loaded `Repo remote` (e.g. `ambroselittle/my-app` → look for a project whose name or path contains `my-app`).

- If one clear match → use it
- If ambiguous → ask the user to pick from the matched candidates
- If no match → ask: "Which project should I create this workspace in?"

### Check for an existing workspace

```
mcp__superset__list_workspaces { "deviceId": "<deviceId>" }
```

If a workspace already exists whose name matches the slug (or contains the ticket token), tell the user: "A workspace `<name>` already exists for this ticket. Want to switch to it instead of creating a new one?"

- **Switch** → use `mcp__superset__switch_workspace` and skip to Phase 4
- **Create new** → continue

---

## Phase 3: Create the Workspace

```
mcp__superset__create_workspace {
  "deviceId": "<deviceId>",
  "projectId": "<projectId>",
  "workspaces": [{
    "name": "<slug>",
    "branchName": "<user-prefix>/<slug>",
    "baseBranch": "main"
  }]
}
```

Capture the returned workspace ID — you'll need it in Phase 4.

If creation fails, report the error and stop — don't improvise.

---

## Phase 4: Switch and Hand Off

Switch to the new workspace so Superset reflects it:

```
mcp__superset__switch_workspace {
  "deviceId": "<deviceId>",
  "workspaceId": "<workspaceId>"
}
```

Then ask: "Workspace ready. Want me to kick off `/plan-work <LINEAR-ID>` in it automatically, or will you do that yourself?"

- **Yes / auto-launch** → use `start_agent_session_with_prompt` to launch plan-work inside the workspace:
  ```
  mcp__superset__start_agent_session_with_prompt {
    "deviceId": "<deviceId>",
    "workspaceId": "<workspaceId>",
    "prompt": "/plan-work <LINEAR-ID>"
  }
  ```
  Confirm: "Plan-work launched in `<slug>`. Switch to the workspace in Superset to see it."

- **No / I'll do it** → "Workspace `<slug>` is ready. Switch to it in Superset and run `/plan-work <LINEAR-ID>` when you're set."

---

## Fallback: No Superset MCP

If any Superset tool call fails with an auth or connection error:

1. Report what happened
2. Fall back to local setup: use `EnterWorktree` to create a worktree, then `git checkout -b <user-prefix>/<slug>`
3. Run `make init` if a Makefile with an `init` target exists
4. Tell the user: "Created branch `<user-prefix>/<slug>` locally. Re-authenticate Superset (`claude mcp auth superset`) for automatic workspace creation next time."

---

## Guidelines

- **Confirm slug before creating anything.** One question, then proceed.
- **Don't plan yet.** `/plan-work` handles intake and discovery — this skill is workspace setup only.
- **One slug, used everywhere.** Same value → workspace name, branch suffix, future the work folder.
