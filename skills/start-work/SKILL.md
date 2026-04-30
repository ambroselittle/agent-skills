---
name: start-work
description: Kick off a new work session from a Linear ticket. Fetches the issue, generates a slug, and creates a Superset workspace (branch + worktree) named after it. Run this before /plan-work when starting from a Linear ticket and you want the workspace created automatically.
argument-hint: "[LINEAR-ID]"
---

# Start Work: Create a Workspace from a Linear Ticket

You are setting up a new work session from a Linear issue. Your job is to fetch the ticket, generate a consistent slug, and create a Superset workspace with the right name — so the user lands in a branch and worktree already tied to the issue.

**Arguments:** $ARGUMENTS

**Pre-loaded context:**
- Ticket ID (from current branch, if any): !`~/.claude/skills/shared/scripts/context.sh ticket-id`
- User branch prefix: !`~/.claude/skills/shared/scripts/context.sh user-slug`

---

## Phase 0: Resolve the Ticket

Determine the Linear issue ID:

- If `$ARGUMENTS` matches `[A-Z]+-\d+` — use it directly
- If `$ARGUMENTS` is empty and the pre-loaded `Ticket ID` is not "none" — use that
- Otherwise: "Provide a Linear issue ID (e.g. `ENG-42`) to start."

Fetch the issue:
```
mcp__claude_ai_Linear__get_issue { "issueId": "<ID>" }
```

Summarize the issue title and description in 1–2 sentences.

---

## Phase 1: Generate the Slug

Apply the standard slug rules:

- Pattern: `<lowercase-team>-<number>-<title-fragment>` — e.g. `eng-42-dark-mode-settings`
- **72-char max.** If a naive kebab-case of the title would exceed it, reformulate a concise but meaningful summary — do not blindly truncate. The `<team>-<number>-` prefix is never shortened.
- This slug is used for: the branch name suffix, the Superset workspace name, and `.work/<slug>/`

Show the proposed slug to the user: `"Slug: eng-42-dark-mode-settings — does this look right?"` Wait for confirmation or a correction before proceeding.

---

## Phase 2: Create the Superset Workspace

Check whether the Superset MCP is available and authenticated:

```
ToolSearch { "query": "select:mcp__superset__*", "max_results": 10 }
```

**If Superset tools are found:**

Use the workspace-creation tool (look for something like `create_workspace`, `new_workspace`, or `create_worktree` in the results). Pass:
- Workspace/worktree name: `<slug>`
- Branch name: `<user-prefix>/<slug>` (e.g. `ambrose/eng-42-dark-mode-settings`)

If the tool requires additional parameters you're unsure about, ask the user rather than guessing.

After creation, confirm: "Workspace `<slug>` created. Switch to it in Superset."

**If Superset tools are not found or return an auth error:**

Fall back to local branch + worktree creation:

1. Check CLAUDE.md for worktree guidance — if present, follow it exactly
2. Otherwise use `EnterWorktree` to create and enter a worktree at the slug path, then run `make init` if a Makefile with an `init` target exists
3. Create the branch: `git checkout -b <user-prefix>/<slug>`

Report what was done: "Created branch `<user-prefix>/<slug>` locally (Superset MCP not available — authenticate it for automatic workspace creation)."

---

## Phase 3: Hand Off

Once the workspace or branch exists:

> "Ready. Run `/plan-work <LINEAR-ID>` to start planning, or just say 'plan work' — the branch is already set up."

Do not run `/plan-work` automatically — the user may want to switch to the new Superset workspace first before planning starts.

---

## Guidelines

- **One slug, used everywhere.** The same slug drives the branch name, workspace name, and future `.work/<slug>/` directory. Get it right in Phase 1.
- **Confirm the slug before creating anything.** A bad workspace name is annoying to fix.
- **Don't plan yet.** This skill is setup only — /plan-work handles intake, discovery, and the actual plan.
