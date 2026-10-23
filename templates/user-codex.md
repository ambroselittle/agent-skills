# Codex Integration

## Skills and tools

Use the installed skill when the user invokes it by name or with `$skill-name`.
Read its `SKILL.md` and use the tools available in the current Codex surface.
Do not invent Claude's `Skill`, `AskUserQuestion`, or task tools. If a workflow
requires an unavailable integration, identify the missing capability explicitly.
Repo instructions and the user's current authorization take precedence over
general workflow suggestions in shared guidance. Read relevant repository
`.claude/rules/` files explicitly; do not assume Codex automatically loads them.
Shared references to the Claude installer config also apply to Codex's
`agent-skills.json`, which overrides inherited preferences.

## Permissions

The agent-skills hooks evaluate the shared rule engine and your private local
rules. `PreToolUse` enforces denials; `PermissionRequest` grants approvals for
supported shell, patch, and MCP inputs. An allowed tool action does not authorize
unrequested work: keep external mutations within the user's requested scope.

Use the normal sandbox escalation request when needed. Do not disguise a command
to get around a policy denial. An `ask` rule blocks at PreToolUse because Codex
does not support that event requesting approval; report the rule's reason.

If an approval prompt appears unexpectedly, inspect the metadata-only log at
`~/.codex/hooks/agent-skills-policy/codex-events.jsonl` (or under `CODEX_HOME`).
A saved trust record or a command succeeding does not prove that a hook ran.
New or changed hook definitions need review through `/hooks`. If an existing
session retains old configuration, restart and resume it before retesting.

## Shared guidance locations

Keep reusable guidance in `templates/user-common.md`, Codex integration details
in `templates/user-codex.md`, and personal additions in `templates/<username>.md`.
The installer writes a managed block to `~/.codex/AGENTS.md`, preserving other
text. Prefer repository `AGENTS.md` linked to its `CLAUDE.md` source where both
tools should read the same project guidance.

Use the active harness name in agent-authored attribution: `Via 🤖 Codex` here.
Claude-only display hooks and terminal status-line scripts are not Codex tools.

## Conversation titles

Use Codex's built-in `/title` display and `/rename` command. Custom Codex title
scripts and nudges are retired. Do not run `window-title set`, start a separate
app-server to rename the conversation, or send terminal escape sequences. Ignore
old cached reminders asking you to use the retired title helper. If the user wants
a live rename, they can use `/rename` in their CLI; do not claim to have performed
that UI action through a shell command.
