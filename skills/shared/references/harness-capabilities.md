# Active Harness Capabilities

Use the tools available in the current Claude Code or Codex session. This reference describes capabilities, not tool names that every surface must provide.

## Skills, questions, and progress

- Invoke another skill with the active harness's native skill mechanism when available. Otherwise read its installed `~/.agent-skills/skills/<name>/SKILL.md` and execute its instructions, resolving relative references against that skill directory. Never invent a `Skill` tool.
- Use the available question tool's current schema, or ask a concise plain-text question. Do not copy another harness's question schema. Wait when a decision or approval is required; unanswered optional questions do not authorize dependent actions.
- Use native progress/task tools when available. Otherwise keep a short checklist in context and maintain the workflow's plan/review artifact. Task tracking must not require a particular tool name.
- Use the active harness's subagent API for delegated work. Pass the complete prompt, read/write scope, and budget. Preserve read-only versus edit-only boundaries, wait for dependent results, and batch independent work within the actual concurrency limit. If delegation is required but unavailable, report that missing capability before replacing it with coordinator work.
- Use a native worktree capability when available, respecting its session/checkout semantics. Otherwise use the repository's documented Git worktree workflow and run subsequent commands in the created directory. Do not claim the current session moved when it did not.

## Model tiers and effort

Map these tiers to models and reasoning-effort settings that the active harness currently exposes. Use its capability/model inventory or current session metadata; never assume identifiers from another provider work here. Keep configured defaults when the harness cannot select a model or effort for a child agent, and report a material capability gap.

| Tier | Work | Mapping |
| --- | --- | --- |
| Low | Mechanical edits, extraction, formatting, bounded lookups | Available economical model with low effort when selectable. |
| Medium | Focused implementation, test authoring, specialist review, concise synthesis | Available general-purpose model with medium effort when selectable. |
| High | Architecture, difficult debugging, conflicting evidence, final cross-domain synthesis | Available strongest reasoning model with high effort when selectable. |

Claude Code and Codex use their own native model/effort selectors. The coordinator maps a tier once per session to the available choices and passes those choices through the actual delegation API. A tier is not a request to change providers, hosts, billing, or permissions.

## Shared context, configuration, and resources

Run the explicit context commands in each skill before relying on their output. Claude's dynamic shell interpolation and metadata extensions are not required by these workflows. Treat invocation arguments as the user's input, whether supplied by native skill arguments or the conversation.

Commands live at `~/.agent-skills/scripts/<skill>/<script>`; resources live at `~/.agent-skills/skills/<skill>/`. Shell commands use the installer-selected `~/.agent-skills/scripts/python`. Source-checkout use before installation may fall back to an existing Python interpreter; it never installs one automatically.

Shared settings live in `~/.agent-skills/config.json`. An explicit `AGENT_SKILLS_CONFIG` selects a different file, with `~` expanded. Before migration, an absent shared config permits reading legacy `~/.claude/agent-skills.json`. Once the shared file exists, it is authoritative. `agents.claude` or `agents.codex` may override shared settings. The active agent comes from an explicit `AGENT_SKILLS_HARNESS`, then Claude session environment (`CLAUDE_SESSION_ID` or `CLAUDE_CODE_SESSION_ID`) or Codex session environment (`CODEX_THREAD_ID`); `CODEX_HOME` alone does not identify a session.

Read effective settings with `bash ~/.agent-skills/scripts/shared/context.sh config` and locate the selected file with `config-path`. Save a setting with `config-set`, passing each key component as a separate argument followed by a JSON value. For example, `config-set team_repos lc '"/absolute/repo"'`. This preserves unrelated settings and updates an existing active-agent override for that top-level setting; otherwise it updates shared defaults. Pass `--shared` before the key components to update common defaults explicitly. Encode values as JSON and quote shell arguments safely.

Read applicable `AGENTS.md`, legacy `CLAUDE.md`, and rules under `.agents/rules/` and `.claude/rules/`. Follow the active harness's instruction precedence; do not duplicate the same linked instruction file in agent prompts. Repository reviewer personas use `.agents/reviewers/` or `.agents/plan-reviewers/`, with legacy `.claude/agents/<group>/` fallback. For each exact reviewer slug, the neutral repository file wins, then the legacy repository file, then the built-in skill persona. Never relocate another repository's existing overrides automatically.

Resolve connected Linear, Notion, and other service actions through tools actually exposed in the current session. Inspect their schemas rather than copying another connector's names or argument fields. If the required integration is missing, report the missing capability; preserve existing failure/continuation rules and never silently omit a required action.
