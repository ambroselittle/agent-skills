---
name: learn
description: Route lessons from a work item to the right destination. Run after corrections or at end of session — reads the ## Lessons section from plan.md, triages each entry, and routes to skill updates, repo-local rules, or user memory. Say "learn" or "/learn".
argument-hint: "[slug]"
---

# Learn: Route Lessons to the Right Place

You are processing lessons captured during a work item and routing each one to its correct destination.

**Arguments:** $ARGUMENTS (optional slug — defaults to current branch slug)

**Pre-loaded context:**
- Current branch: !`~/.claude/skills/shared/scripts/context.sh current-branch`

---

## Step 0: Scan Conversation for Uncaptured Lessons

Before reading the plan, do a quick scan of the current conversation context for any corrections, pivots, or insights that weren't explicitly recorded as `## Lessons` entries.

Look for signals like:
- "actually, do X instead" / "no, not like that"
- A correction the user made to your approach or output
- A moment where you got something wrong and then fixed it
- An assumption that turned out to be incorrect

For each one found, check whether it's already captured in plan.md's `## Lessons` section. If not, propose adding it:

> "I noticed this correction wasn't captured: [brief description]. Add it to Lessons before routing? (y/n)"

On confirmation, append the entry to the `## Lessons` section. If declined or if no uncaptured lessons are found, continue.

**Note:** This step is session-dependent — it only works if `/learn` is run in the same session where the work happened. If run in a fresh session, skip this step silently.

---

## Step 1: Find the Work Item

If a slug was provided in `$ARGUMENTS`, use it directly.

Otherwise, derive from the current branch: strip the user prefix (everything up to and including the first `/`). Example: `ambrose/42-add-learn-skill` → `42-add-learn-skill`.

Read `.work/<slug>/plan.md`.

- **No plan found**: "No plan found for `<slug>`. Provide a slug as an argument, or make sure you're on the right branch." Stop.
- **Plan found but no `## Lessons` section**: "No `## Lessons` section found in `plan.md`." Stop.
- **Lessons section found but empty** (only the comment placeholder, or blank): "No lessons to route — the Lessons section is empty." Stop. No edits, no changes.

---

## Step 2: Extract Lesson Entries

Parse the `## Lessons` section. Entries are bullet-point items (`- ...`). Ignore comment lines (lines starting with `<!--`).

If no bullet-point entries are found after ignoring comments: "No lesson entries found." Stop.

List the extracted entries:

```
Found N lesson(s) to route:
1. <entry text>
2. <entry text>
...
```

---

## Step 3: Triage Each Lesson

For each entry, determine the routing destination based on the content:

| Route | Signals |
|-------|---------|
| **Skill update** | Mentions a specific skill by name (hack, ship, start-work, code-review, plan-review, fix-tests, learn) or describes a behavioral change to a skill's workflow |
| **Repo-local rules** | Mentions `.claude/rules/`, a local rule, or behavior specific to this repo |
| **User memory** | Personal preference, individual working style, or anything that doesn't clearly belong to a specific skill or repo |

If classification is ambiguous, default to **User memory** — it's the right home for anything personal or unclear.

Present the triage plan before taking any action:

```
Routing plan:
1. [Skill update → ~/.claude/skills/start-work/SKILL.md] "<entry>"
2. [Repo-local rules → .claude/rules/skill-authoring.md] "<entry>"
3. [User memory] "<entry>"
...
Proceed? (y/n)
```

If the user wants to adjust any classification, update before continuing.

---

## Step 4: Execute Each Route

Work through the entries one at a time.

---

### Route: Skill update

1. Identify the skill name from the entry (e.g., "hack skill" → `hack`, "start-work" → `start-work`).
2. Read `~/.claude/skills/<name>/SKILL.md`.

**If skill found:**

- Read the current SKILL.md content.
- Propose the change: describe which section to update and show the exact text to add or modify.
- Ask: "Apply this change to `~/.claude/skills/<name>/SKILL.md`? (y/n)"
- On confirmation, apply with the Edit tool.
- If declined, mark as **unrouted**.

**If skill not found** (`~/.claude/skills/<name>/SKILL.md` doesn't exist):

"Could not find skill `<name>` at `~/.claude/skills/<name>/SKILL.md`. Skipping — leaving in plan.md." Mark as **unrouted**.

---

### Route: Repo-local rules

1. Identify which rules file is relevant from the lesson text (e.g., `.claude/rules/skill-authoring.md`). If it's unclear, ask the user which file to update.
2. Read the current file content (create if it doesn't exist).
3. Propose the change: describe which section to update and show the exact text to add or modify.
4. Ask: "Apply this change to `.claude/rules/<file>`? (y/n)"
5. On confirmation, apply with the Edit tool (or Write if it's a new file).
6. If declined, mark as **unrouted**.

---

### Route: User memory

For entries that are personal, stylistic, or don't clearly belong to a specific skill or repo — write a user memory entry.

1. Determine the memory type: `feedback` (how to approach work), `user` (about the user's role/preferences), `project` (ongoing work context), or `reference` (where to find things).
2. Draft the memory content following the format for that type (see auto-memory instructions in your context).
3. Show the proposed memory and ask: "Save this to user memory? (y/n)"
4. On confirmation, write to the appropriate memory directory.
5. If declined, mark as **unrouted**.

---

## Step 5: Confirm and Clean Up

After all entries are processed, show a summary:

```
Routing summary:
- 2 entries routed (1 skill edit, 1 user memory)
- 1 entry unrouted (skill not found)

Unrouted entries remain in plan.md.
```

If any entries were successfully routed, ask: "Remove successfully routed entries from the Lessons section of plan.md? (y/n)"

On confirmation: edit `.work/<slug>/plan.md` to remove only the successfully-routed entries from the `## Lessons` section, leaving the comment placeholder and any unrouted entries in place.

If no entries were routed, no change to plan.md.

---

## Guidelines

- **Never modify plan.md without confirmation.** The Lessons section is the source of truth — don't clear anything until the user confirms the routing summary.
- **Never edit a skill or rules file without showing the proposed change.** Always read the file first; always show what would change before applying.
- **Partial failures are fine.** If some lessons are routed and some aren't, that's a valid outcome. Leave unrouted entries in plan.md for the next run.
- **When classification is ambiguous, ask.** Don't silently guess the wrong route.
