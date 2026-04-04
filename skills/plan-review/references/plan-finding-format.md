# Plan Review Finding Format

Shared format for plan review findings. Every plan reviewer MUST output findings using this exact format.

## Finding Types

Unlike code review (which flags defects), plan review findings fall into three types that drive different actions:

- **MISMATCH** — Something in the plan conflicts with or is blocked by reality: wrong assumptions about current code, work that's already done, an interface that no longer exists. These are not optional — coordinator must surface them to the user and get confirmation before proceeding.
- **IMPROVEMENT** — A clearly better approach, phasing, or framing that the coordinator should incorporate directly. Improvements are changes, not options. Coordinator rolls them in and notes what changed.
- **ALTERNATIVE** — An approach worth considering alongside the plan's current direction. Neither clearly better nor clearly worse — depends on tradeoffs the user should weigh. Coordinator adds these to the plan's "Alternatives Considered" section.

## Finding Template

```
- **[TYPE] Brief title**
- **Reviewer:** <agent-name>
- **Description:** What you found — be specific, reference the plan section and relevant files
- **Why it matters:** The consequence of not addressing this
- **Recommendation:** What to do (MISMATCH: what the correct state is; IMPROVEMENT: what the revised approach looks like; ALTERNATIVE: what the tradeoff is vs. the current approach)
- **Confidence:** high | medium | low
```

## Output Structure

Each reviewer must return findings grouped by type:

```
## MISMATCHES
(findings, or "None")

## IMPROVEMENTS
(findings, or "None")

## ALTERNATIVES
(findings, or "None")
```

If you find nothing in a category, say "None" explicitly — do not omit the section. A clean review is a good outcome; do not manufacture findings.

## Coordinator Synthesis Rules

After all reviewers return:

1. **Mismatches first.** If any MISMATCH findings exist, surface them before presenting the plan. Describe each: what the plan says vs. what the code shows. Ask the user to confirm direction before proceeding. Do not present the plan until mismatches are resolved.

2. **Incorporate improvements silently.** For each IMPROVEMENT, update the plan in place. At the end of the plan, add a `## Changes from Initial Draft` section listing what was changed and which reviewer suggested it. Keep it brief — one line per change.

3. **Surface alternatives in the plan.** For each ALTERNATIVE, add it to an `## Alternatives Considered` section in the plan. Format: the alternative approach, its tradeoffs vs. the current direction, and which reviewer surfaced it. Present this section when walking the user through the plan — they decide whether to adopt one, combine, or proceed as-is.
