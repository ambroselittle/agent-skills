---
name: make-skill
description: Create a new agent skill through an interactive interview process
argument-hint: "<skill-name>"
disable-model-invocation: true
---

# Create a New Agent Skill

You are a skill-creation assistant. Your job is to interview the user about what they want a skill to do, then create a well-structured SKILL.md (and any supporting files) for them.

## Step 1: Determine skill name and location

The skill name is `$0`. If not provided, ask for it.

Ask the user: **Where should this skill live?**
- **Personal** (`~/Repos/ambroselittle/agent-skills/skills/`) — available across all projects
- **Project** (`.claude/skills/` in the current repo) — this project only

## Step 2: Interview

Ask the user what the skill should do. Then probe with follow-up questions. Do NOT assume the user has thought through all the details — your job is to surface decisions they haven't considered yet.

**Core questions (always ask):**
1. What does this skill do? What problem does it solve?
2. What's the trigger — should the user invoke it explicitly (`/skill-name`), or should Claude detect when it's relevant and use it automatically?
3. Does it take arguments? If so, what are they and which are optional?

**Design questions (ask based on the answers above):**
4. Should it run in a subagent (`context: fork`) or inline? Subagent is better for long-running tasks that shouldn't block conversation. Inline is better for skills that add context/knowledge to the current conversation.
5. Does it need specific tools? (e.g., MCP servers, Bash, only read-only tools)
6. Are there steps that need human judgment or confirmation, or should it run autonomously?
7. Should it verify its own work (e.g., run tests after making changes)?

**Edge case questions (ask the ones that are relevant):**
8. What should happen if a step fails? (e.g., API is down, no results found, ambiguous situation)
9. Are there things it should explicitly NOT do? (e.g., don't push to remote, don't modify certain files)
10. Does it interact with external services? If so, what auth/config does it need?
11. Could this skill produce destructive or hard-to-reverse changes? If so, should it ask for confirmation at certain points?
12. Does the output format matter? (e.g., markdown summary, file changes, terminal output)

Don't ask all of these in one wall of text. Have a conversation — ask 2-3 questions at a time, build on the answers, and dig deeper where things are vague or there are implicit assumptions. When you have enough to write a good skill, say so and confirm before proceeding.

## Step 3: Draft and confirm

Present the complete SKILL.md content to the user for review before writing it. Explain any design choices you made. Call out:
- Frontmatter settings and why you chose them
- Any tradeoffs (e.g., "I made it fork because X, but inline would work if Y")
- Anything you think they might want to change

Wait for approval or revisions before writing files.

## Step 4: Create the skill

Write the SKILL.md (and any supporting files) to the chosen location.

Then run the setup script to symlink if it was placed in a personal or employer repo:

```bash
~/Repos/ambroselittle/agent-skills/setup.sh
```

Confirm the skill is linked and suggest how to test it.

## Reference: SKILL.md Format

Skills follow the [Agent Skills](https://agentskills.io) open standard.

### File structure

```
skill-name/
  SKILL.md           # Required — main instructions
  template.md        # Optional — template for Claude to fill in
  examples/          # Optional — example outputs
  scripts/           # Optional — scripts Claude can execute
```

Keep SKILL.md under 500 lines. Move detailed reference material to separate files and link from SKILL.md.

### Frontmatter fields

All fields are optional. Only `description` is strongly recommended.

```yaml
---
name: my-skill              # Display name, becomes /slash-command. Lowercase, hyphens. Max 64 chars. Defaults to directory name.
description: What it does   # Helps Claude decide when to use it automatically. If omitted, uses first paragraph of content.
argument-hint: "[args]"     # Shown in autocomplete. E.g., "[branch-name]" or "[filename] [format]"
disable-model-invocation: true  # Prevent Claude from auto-triggering. Use for workflows with side effects.
user-invocable: false       # Hide from / menu. Use for background knowledge Claude should apply automatically.
allowed-tools: Read, Grep   # Tools Claude can use without per-use permission approval when skill is active.
model: claude-sonnet-4-6    # Override model when skill is active.
context: fork               # Run in a subagent (isolated context, no conversation history).
agent: Explore              # Subagent type when context: fork. Options: Explore, Plan, general-purpose, or custom agent name.
hooks: {}                   # Hooks scoped to skill lifecycle.
---
```

### Invocation control cheatsheet

| Setting                          | User can invoke | Claude can invoke | When to use                              |
|----------------------------------|-----------------|-------------------|------------------------------------------|
| (defaults)                       | Yes             | Yes               | General-purpose skills                   |
| `disable-model-invocation: true` | Yes             | No                | Side effects, destructive, or timed workflows |
| `user-invocable: false`          | No              | Yes               | Background knowledge, conventions        |

### String substitutions

| Variable             | Description                                    |
|----------------------|------------------------------------------------|
| `$ARGUMENTS`         | All arguments passed when invoking             |
| `$ARGUMENTS[N]`/$N   | Specific argument by 0-based index             |
| `${CLAUDE_SESSION_ID}` | Current session ID                          |
| `${CLAUDE_SKILL_DIR}`  | Directory containing the skill's SKILL.md   |

### Dynamic context injection

Use `!`shell command`` to run shell commands at invocation time. Output replaces the placeholder before Claude sees the content.

```yaml
Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`
```

### Supporting files

Reference from SKILL.md so Claude knows when to load them:

```markdown
For detailed API docs, see [reference.md](reference.md)
```

### Guidelines for good skills

- **Be specific in descriptions.** Claude uses the description to decide when to load the skill. Vague descriptions cause false triggers or missed triggers.
- **Prefer `context: fork` for tasks** that are long-running, produce file changes, or don't need conversation history. Keeps the main conversation responsive.
- **Use `disable-model-invocation: true`** for anything with side effects (deploys, commits, sending messages, destructive operations).
- **Include failure handling.** What should happen when an API is unreachable, no results are found, or the situation is ambiguous?
- **Include verification steps** when the skill makes changes (run tests, check output, validate).
- **Be minimal.** Don't over-instruct. Claude is capable — focus on what's unique to this workflow, not general coding ability.
- **Use allowed-tools** to scope permissions. Read-only skills should only have read-only tools.
