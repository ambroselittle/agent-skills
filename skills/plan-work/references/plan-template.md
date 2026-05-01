# Plan Document Template

Use this format for all plans saved to `<work-folder>/plan.md`.
This structure is read by `/do-work`, `/plan-review`, `/code-review`, and `/super-work`.

---

```markdown
---
skill: plan-work
linear-issue: <LINEAR-ID or "none">
github-issue: <GITHUB-ISSUE-NUMBER or "none">
notion-source: <NOTION-URL or "none">
branch: <branch-name or "none">
status: planning
---

# Plan: <title>

> <One-paragraph summary of what this work does and why>

## Context

- **Issue:** [ENG-42](https://linear.app/...) — <title>  (omit if no issue)
- **Spec:** [Page title](https://notion.so/...) — <one-line summary>  (omit if no Notion source)
- **Goal:** <what "done" looks like — specific and verifiable>
- **Scope:** <what's in and what's explicitly out>

## Relevant Files

| File | Repo | Role |
|------|------|------|
| path/to/file.ts | loancrate/web | <why it matters> |

(Omit the Repo column for single-repo plans)

## Phases

### Phase 1: <name>

**Repo:** loancrate/api
(Omit the Repo line entirely for single-repo plans or when all phases are in the same repo)

**Goal:** <what this phase delivers as a whole>

**Tasks:**
- [ ] `<commit message>` — <what this task does; name the files and what changes>
- [ ] `<commit message>` — <what this task does>

**Verify (after all tasks in phase):**
- [ ] <concrete verify step — test command or manual check>

---

### Phase 2: <name>

**Repo:** loancrate/web
(Different repo = separate workspace; /do-work will filter phases by current repo)

**Goal:** ...

**Tasks:**
- [ ] ...

**Verify:**
- [ ] ...

---

## Verification Commands

If command supports it, pass related files — do not run on entire codebase; let PR CI handle that.

- <lint command>
- <typecheck command>
- <test command>

## Open Questions

- <anything uncertain that needs answering before or during implementation>

## Out of Scope

- <things that came up in discovery but aren't part of this work>

## Lessons

<!-- Populated during the work by /do-work. Each entry: what happened, what was learned. -->
```

---

## Multi-repo notes

- `**Repo:**` on a phase tells `/do-work` which repo that phase belongs to. Omit it entirely for single-repo work — its absence means "same repo as where you're running."
- `/super-work` reads the unique set of repos across all phases and asks which to open if there are multiple.
- The `Repo` column in Relevant Files is optional — include it when files span repos, omit it otherwise.
