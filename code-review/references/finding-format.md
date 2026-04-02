# Standard Finding Format

Shared format for review findings. Every reviewer MUST output findings using this exact format.

## Finding Template

```
- [x] **F1. [SEVERITY] Finding title**
- **File:** path/to/file.ts:L42-L55 — [Open](../../path/to/file.ts#L42-55)
- **Reviewer:** <agent-name> (or comma-separated list if multiple reviewers flagged it)
- **Description:** What the problem is
- **Why it matters:** Impact if not addressed
- **Suggestion:** How to fix it (be specific — include code snippets when helpful)
- **Confidence:** <label> (<score>) — e.g., `high (95)`, `medium (78)`, `low (55)`. See review-discipline.md for band definitions.
- **Open question:** (optional) If uncertain, flag for user input
- **Instructions:** 
```

**Finding status lifecycle:**

- `[x]` — act on this (pre-checked, opt-out model)
- `[ ]` — flagged but low confidence; reviewer opts in if they agree
- `[ ]` → `[skipped]` — user unchecked
- `[x]` → `[fixed]` — edit applied
- `[fixed]` → `[verified]` — fix confirmed by verification (tests/typecheck/lint)
- `[x]` → `[could-not-prove]` — attempted but could not write a proof test after retries
- `[will-not-do]` — intentionally not addressing (with justification)
- `[deferred]` — valid but out of scope for this PR
- `[clarification-needed]` — ambiguous, needs follow-up with reviewer
- `[already-resolved]` — was fixed before processing

Severity tag (`[BLOCKER]`, `[ISSUE]`, etc.) and sequential ref ID (`F1`, `F2`, ...) go on the title line.

## Severity Levels

- **BLOCKER** — Must fix. Bugs, security vulnerabilities, data loss risks, broken functionality.
- **ISSUE** — Should fix. Behavioral defects (wrong behavior even if no crash), scope overreach (operating on broader data, users, or systems than intended), violations of team standards, maintainability problems, missing error handling. **Key test:** if the code does something unintended at runtime (excessive events, wrong data submitted, stale UI, queries hitting unintended targets), it's an ISSUE minimum.
- **SUGGESTION** — Consider fixing. Improvements that would make code better but aren't wrong as-is.
- **NIT** — Take it or leave it. Style preferences, minor naming quibbles, optional polish.

## Informational Notes (no action required)

For purely informational observations — things worth knowing but that don't require any change — use this format instead of a full finding:

```
- **[NOTE]** [component/file] Brief observation — why it's worth knowing
```

Notes are collected into a separate `## Informational Notes` section in the review document. They do not get ref IDs, checkboxes, or Instructions fields. Only use this when you are certain no change is needed. If there is any chance the observation warrants action, it's at least a NIT.

## File References

Use clickable editor links with paths relative to the review document location. Format: `[Open](../../path/to/file.ts#L42-55)`. Single lines: `#L42`. Ranges: `#L42-55`.
