---
name: sync-guidance
description: Sync shared user guidance between installed Claude Code and Codex agents and the agent-skills source repo. Preserves protected managed blocks and proposes generic improvements through a PR.
argument-hint: "[inbound|outbound|both]"
---

# Sync Guidance

Sync user guidance between this machine and `~/.agent-skills/source`. Use the active agent’s native tools as described in [harness capabilities](../shared/references/harness-capabilities.md).

**Input:** `inbound` applies approved local additions, `outbound` proposes source improvements, and `both` (default) performs both directions. The source checkout is resolved through the installed alias, independently of the project invoking this skill.

## Step 0: Load and inspect context

Run each helper separately:

```bash
~/.agent-skills/scripts/sync-guidance/context.sh guidance
```

```bash
~/.agent-skills/scripts/sync-guidance/context.sh repo-rules
```

```bash
~/.agent-skills/scripts/sync-guidance/context.sh git-status
```

`guidance` reads existing `~/.claude/CLAUDE.md` and `${CODEX_HOME:-~/.codex}/AGENTS.md`. Each record identifies the agent, complete content, protected fences, and every unmanaged range, including text before and between fences. Read all records. A file not present is skipped; do not create an agent installation as a side effect.

Protected XML-style blocks belong to their managing tool or organization. Read them for generalizable insights, but never edit inside them. Unclosed opening fences are protected through the end of the file. Preserve every existing unmanaged range and its placement; the personal section is not limited to text after the last fence.

`repo-rules` separates `user-common.md` from each agent’s integration template. Compare each installed file with the common template, applicable integration template, personal source overlay, and relevant project rules. Do not copy Claude-only instructions into Codex guidance or vice versa.

## Step 1: Inbound — Source to installed agents

Skip for `outbound`.

Identify substantive gaps against each complete installed file; paraphrased guidance already present counts as covered. Managed source changes belong in the templates and must be applied through setup, never copied into personal text to work around managed ownership. Refresh those changes with `bash ~/.agent-skills/source/setup.sh guidance`, after showing the proposed changes and receiving confirmation for this skill’s writes.

For approved personal additions, show the exact destination and proposed text first. Append only outside protected fences, preserving all existing personal text. Route shared additions to both already-installed agents when approved; keep agent-specific additions in the appropriate file. Do not infer permission to overwrite personal notes or employer-managed content.

## Step 2: Outbound — Installed agents to source

Skip for `inbound`.

Scan the complete installed files, including protected sections, for novel guidance. Extract only generalizable practices; omit employer-specific names, internal tooling, credentials, and proprietary context. Compare substance across both agents and source templates to avoid duplicates.

Present each candidate with its destination and proposed wording. Universal behavior belongs in `templates/user-common.md`; agent integration details in `templates/user-claude.md` or `templates/user-codex.md`; personal preferences in the selected personal template. Repo-wide directives belong in `.claude/rules/` with appropriate `paths` frontmatter, and orientation belongs in `CLAUDE.md` linked by `AGENTS.md`.

Wait for approval before writing. Work in the source checkout or an isolated source worktree, preserving unrelated local changes. Use the configured branch prefix from `~/.agent-skills/config.json`. Verify, commit, push, and open a PR using the repo’s PR workflow and `/author-message`. Do not merge.

## Step 3: Report

Report the installed destinations updated and the PR URL, if any. State any missing input needed to finish. Keep the result brief.

## Boundaries

- Protected fences are read-only, including incomplete fences.
- Preserve all unmanaged text before, between, and after managed blocks.
- Show proposed changes and obtain confirmation before this skill writes guidance.
- Setup owns managed blocks; source templates remain their single maintained copy.
- Publish only generic guidance approved by the user.
