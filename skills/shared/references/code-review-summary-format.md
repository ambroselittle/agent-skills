# Code Review PR Comment Format

This is the exact format for the PR comment posted after a code review cycle. Follow it precisely
— do not invent a different layout.

## Format

Wrap the entire comment in a collapsible `<details>` block:

```markdown
<!-- code-review: <review-sha> -->
<details>
<summary>Code Review — X findings (Y fixed, Z skipped)</summary>

**Reviewed:** YYYY-MM-DD UTC | **Reviewers:** <comma-separated list> | **Scope:** <incremental from <sha> | full PR>

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| F1 | BLOCKER | Brief description of the finding | One-line resolution |
| F2 | ISSUE | Brief description | Skipped — reason |
| F3 | SUGGESTION | Brief description | Deferred |
| F4 | NIT | Brief description | Fixed |

Fix commit: https://github.com/org/repo/commit/<sha>

> N findings suppressed — already raised by PR reviewers

</details>
```

## Rules

- **Summary line:** `Code Review — X findings (Y fixed, Z skipped)` where X = total actionable
  findings, Y = fixed+verified, Z = skipped+will-not-do. Deferred counts separately if any.
- **Reviewers:** list the agent names that ran, comma-separated (e.g., `security, devdocs, testing, coordinator`)
- **Scope:** `incremental from <sha>` or `full PR`
- **Finding column:** one brief phrase — what the problem was, not the full description
- **Status column:** one line with brief resolution note
- **Fix commit:** link to the single fix commit SHA. If no fixes were made, omit this line.
- **Marker comment:** every PR comment MUST start with `<!-- code-review: <review-sha> -->` where
  `<review-sha>` is the 7-char short SHA from the review doc filename (the HEAD at review start,
  e.g. `074e269` from `rustic-net.review.2026-03-30-074e269.md`). This is the identity key — it
  ties the comment to a specific review round regardless of whether fixes were made.
- **New comment vs update:** each review round posts a **new** comment. Only update an existing
  comment if you are resuming a partially-posted round (i.e., you find a marker matching the
  current review SHA). Search with `gh api` for existing comments containing the marker
  before posting.
- **Human feedback suppression:** if findings were suppressed because they matched existing PR
  feedback (especially feedback with responses indicating the concern was already addressed or
  intentional), add a single summary line after the findings table:
  `> N findings suppressed — already raised by PR reviewers`. Omit this line if N = 0. Do NOT
  include the full `## Human Feedback Cross-Reference` table from the review doc — that is internal.
- **Omit:** frontmatter, the `## Review Notes` section, the `## Human Feedback Cross-Reference` section, full finding descriptions, suggestions, instructions fields, and any internal metadata.
- **If no PR exists:** skip posting entirely — the review doc stays local.
- **Timezone:** always UTC — team artifact, not the poster's local time

## What this comment is NOT

This is a summary of the code review workflow outcome — what was found, what was fixed, what was
skipped. It is not a response to PR reviewer comments.
