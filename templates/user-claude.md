# Claude Code Integration

## Slash Commands Are Skill Invocations

When a user message starts with `/skill-name` (e.g., `/do-fixes`, `/code-review`,
`/do-work`), **always invoke it via the Skill tool** — even if the harness didn't expand it into a
`<command-name>` tag. The harness may not recognize newly added skills until `setup.sh` is re-run,
or the command may arrive unexpanded in remote/dispatch sessions. Treat any message starting with
`/<word>` that matches a known skill name as a skill invocation. If the Skill tool rejects it
(skill not found), tell the user and suggest running `setup.sh` to re-link skills.

## Keep the Window Title Topical

Each session's terminal title is a per-session label, so several open Claude windows can be told
apart at a glance while tabbing between them. Set it with:

```sh
~/.claude/scripts/window-title set "Ghostty window titles"
```

Three or four words naming what the conversation is _about_ — "Ghostty window titles", "custom
fields at depth", "Datadog monitor cleanup". A tab shows a topic, not a sentence, so no summaries and
no leading fragment of the first prompt.

- **Never put an identifier in the title** — no Linear keys (`LC-26196`), PR or issue numbers, branch
  names, or commit SHAs. They read as noise while scanning and force the reader to look up what they
  refer to. Name the subject instead: "custom fields at depth", not "LC-27615". If the whole session
  is one ticket, the title is what that ticket is _about_.
- Set it as soon as the topic is clear, usually on the first prompt. Do it quietly as part of the
  turn — don't announce it or ask permission.
- Revisit only when the subject genuinely shifts, not every turn. A hook reminds you when the title
  is missing or has gone stale, so there's nothing to track.
- **When the user names the title themselves, use `pin`, not `set`:**
  `~/.claude/scripts/window-title pin "their words"`. A pinned title is theirs — never revise it,
  and it silences the reminders for the rest of the session.

## Shared runtime

Read preferences from `~/.agent-skills/config.json` and load skill context explicitly through
`~/.agent-skills/scripts/`. Use the capability tiers in
`~/.agent-skills/skills/shared/references/harness-capabilities.md`; choose only models and tools
available in this Claude Code session. Legacy configuration is migrated by setup, which retains
the original files.
