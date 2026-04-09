---
name: sync-guidance
description: Sync Claude guidance between machines. Reads ~/.claude/CLAUDE.md on the current machine, diffs it against this repo's rules, and does two things — (1) updates the personal (unfenced) section of CLAUDE.md with anything new from the repo, and (2) proposes a PR to the repo with any novel guidance found on this machine. Run this on a work machine after cloning the repo to stay in sync.
argument-hint: "[inbound|outbound|both]"
---

# Sync Guidance

You are syncing Claude guidance between this machine's `~/.claude/CLAUDE.md` and the agent-skills repo. The goal is to keep personal guidance in sync across machines without touching anything managed by others.

**Arguments:** $ARGUMENTS
- `inbound` — only update `~/.claude/CLAUDE.md` from repo (repo → this machine)
- `outbound` — only propose PR with novel guidance from this machine (this machine → repo)
- `both` (default) — do both directions

**Pre-loaded context:**

- CLAUDE.md contents and fence map: !`~/.claude/skills/sync-guidance/scripts/context.sh claude-md`
- Repo rules and shared template: !`~/.claude/skills/sync-guidance/scripts/context.sh repo-rules`
- Repo git status: !`~/.claude/skills/sync-guidance/scripts/context.sh git-status`

---

## Step 0: Understand the Landscape

From the pre-loaded context, identify:

1. **Fenced blocks** in `~/.claude/CLAUDE.md` — these are managed by others (employer, other tools). Note their tags and line ranges. You will **read** these for insights but **never write to them**.
2. **Personal section** — everything after the last fence closing tag. This is yours to update.
3. **Repo rules** — the current `.claude/rules/*.md` files and `templates/user-claude.md` in this repo.

Print a brief orientation:
```
CLAUDE.md: <N> lines total
  Fenced blocks: <list tag names and line ranges, or "none">
  Personal section: lines <N>–end (<M> lines)

Repo: <N> rule files found
```

---

## Step 2: Inbound — Repo → This Machine

*Skip if argument is `outbound`.*

**Goal:** Add anything from the repo's guidance that isn't already reflected anywhere in `~/.claude/CLAUDE.md` (personal section or fenced sections — check the whole file).

### 2a. Identify gaps

Compare repo guidance (rules + shared template) against the full CLAUDE.md content:

- For each rule file and each meaningful section of `user-claude.md`: check if the substance is already present somewhere in CLAUDE.md (exact or paraphrased — don't flag things already covered)
- Build a list of genuine gaps: guidance in the repo not reflected anywhere in CLAUDE.md

### 2b. Propose additions

For each gap, draft the text to add to the personal section. Group related items. Keep additions concise — these are personal reminders, not full rule docs.

Present the proposed additions:

```
Inbound additions to personal section of ~/.claude/CLAUDE.md:

1. [from rules/skill-authoring.md]
   > AskUserQuestion requires 2–4 options per question...

2. [from rules/python-packaging.md]
   > Use [dependency-groups] not [tool.uv] dev-dependencies...

Apply these? (yes / select / skip)
```

- `yes` — apply all
- `select` — go through each one individually  
- `skip` — skip inbound entirely

### 2c. Apply

Append approved additions to the personal section of `~/.claude/CLAUDE.md`. Add a comment header: `## Synced from agent-skills (<date>)` before the block if adding multiple items.

---

## Step 3: Outbound — This Machine → Repo

*Skip if argument is `inbound`.*

**Goal:** Find novel guidance on this machine not yet in the repo, and propose it as new or updated rule files via a PR.

### 3a. Identify novel guidance

Scan the entire `~/.claude/CLAUDE.md` — both fenced and personal sections — for guidance not already present in the repo's rules or shared template.

When reading fenced sections managed by others:
- Extract generalizable insights (patterns, practices, constraints) — not employer-specific content
- Rephrase to be generic and universally applicable
- Skip anything too specific to that employer's stack/context

Build a list of candidates: novel guidance worth adding to the repo.

### 3b. Triage candidates

For each candidate, determine:
- Is this genuinely novel vs. already covered (even loosely) in the repo?
- Is it generalizable, or too specific to this machine/context?
- Where should it live: new rule file, addition to existing rule file, or update to `templates/user-claude.md`?
- If a rule file: what `paths` frontmatter scope applies?

Present the triage:

```
Outbound candidates:

1. [new rule: .claude/rules/foo.md, paths: ["**/*.ts"]]
   > <proposed content summary>

2. [add to: .claude/rules/skill-authoring.md]
   > <proposed addition>

3. [skip — too employer-specific]
   > <reason>

Proceed with candidates 1 and 2? (yes / select / skip)
```

### 3c. Write rule files

For approved candidates:
- Write or update the rule files in the repo
- Apply correct `paths` frontmatter (consult `.claude/rules/rule-authoring.md`)
- Keep content generic and universally applicable — no employer names, internal tool names, or proprietary context

### 3d. Open PR

If any rule files were written:

1. Create a branch: `ambrose/sync-guidance-<date>` (use ISO date, e.g. `2026-04-08`)
2. Commit: `"sync-guidance: add rules from work machine"`
3. Open PR to main with a summary of what was added and where it came from (described generically)

---

## Step 4: Summary

Print a clean summary of what was done:

```
Sync complete.

Inbound: added N items to personal section of ~/.claude/CLAUDE.md
Outbound: PR opened at <url> with N new/updated rule files

Nothing was modified inside fenced blocks.
```

---

## Guidelines

- **Read-only for fenced blocks.** Never edit content between fence tags, regardless of which tool manages them.
- **Write boundary is the personal section.** All edits to CLAUDE.md go after the last closing fence tag.
- **Generic outbound only.** Anything going into the repo must be free of employer-specific context. Rephrase before proposing.
- **Diff before proposing.** Don't propose additions already covered — check substance, not just exact text.
- **No auto-apply.** Always show proposed changes and get confirmation before writing anything.
