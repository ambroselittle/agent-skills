# Mark a Linear Ticket "In Progress"

Procedure for transitioning a Linear ticket to its team's "in progress" status when work begins. Used by `/start-work`, `/super-work`, and any other skill that initiates work on a ticket.

**Skip this entirely if no Linear ticket is involved** (e.g. slug-only / free-text path).

---

## Step 1 — Check current state

Inspect the current state from the available Linear issue-fetch tool. Discover its schema and normalize the state type/name described below; connector field names may differ.

- `state.type === "started"` → already in progress (or in a downstream started state like "In Review"). **Skip the transition.** Don't regress a deliberate forward move.
- `state.type === "completed"` or `"canceled"` → ask: "Ticket `<TICKET>` is `<state.name>`. Continue anyway?" If yes, **skip the transition** and proceed. If no, stop the whole skill.
- Otherwise (`backlog`, `unstarted`, `triage`) → continue to step 2.

---

## Step 2 — Resolve the team's "in-progress" state ID

Read `linear_team_statuses.<TEAM>.in-progress` from the effective shared config (`bash ~/.agent-skills/scripts/shared/context.sh config`), where `<TEAM>` is the **uppercase** team prefix from the ticket ID (e.g. `LC` for `LC-12345`).

The schema is intentionally semantic and extensible — future transitions (`in-review`, `done`, …) slot in alongside `in-progress`:

```json
{
  "linear_team_statuses": {
    "LC": {
      "in-progress": "<state-uuid>"
    }
  }
}
```

### If configured

Use the saved state ID. If the transition later fails with "state not found" (e.g. status was deleted in Linear), invalidate the cached value and re-run step 2 from scratch.

### If not configured

Discover the team's issue statuses with the available connected Linear tool, using its actual schema. Resolve the team from the issue-fetch response; connector field names and accepted team identifiers may differ.

Filter to statuses where `type === "started"`:

- **Exactly one** → use it, save silently. Report: "Saved `<TEAM>.in-progress` = `<state-name>`."
- **Multiple** (e.g. "In Progress", "In Review", "In QA") → ask: "For team `<TEAM>`, which status means _actively working_? [list options]". Save the chosen state ID.
- **Zero** → warn "No `started` status found for team `<TEAM>` — skipping transition." Continue the calling skill without transitioning.

Save to config:

```bash
bash ~/.agent-skills/scripts/shared/context.sh config-set linear_team_statuses '<TEAM>' in-progress '"<state-id>"'
```

Encode values as JSON and quote arguments safely. This preserves unrelated teams and honors the selected config and any existing active-agent override.

---

## Step 3 — Transition the issue

Update the issue to the resolved status using the available connected Linear tool and its actual schema.

Report: "Marked `<TICKET>` → `<state-name>` in Linear."

If the API call fails (auth error, network, permission), **report the error and continue** — don't block the calling skill on a Linear hiccup. The user can move the ticket manually.

---

## Extension notes

When a future skill needs a different transition (e.g. `/finish-work` → mark `in-review`), reuse this same lookup pattern with a different semantic key:

```
linear_team_statuses.<TEAM>.in-review
linear_team_statuses.<TEAM>.done
```

The discovery logic stays the same — filter `list_issue_statuses` results by the appropriate `type` (`started` for in-progress / in-review work, `completed` for done) and ask the user to pick if multiple match.
