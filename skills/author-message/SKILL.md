---
name: author-message
description: Draft outbound prose posted on the user's behalf — PR descriptions, PR review comments, Slack messages, Linear and Notion comments or issue bodies, commit messages. Use this BEFORE writing any message to an external service, not after. Produces a draft that leads with the conclusion and holds supporting detail in reserve.
argument-hint: "[pr-body|pr-comment|slack|linear|notion|commit]"
---

# Author an outbound message

You are about to post something a human will read. Draft it here first.

## The rule

Give the reader the decision and enough to act on it. Everything else is available if they ask.

## Selection, not compression

The failure this skill exists to prevent is not long sentences. It is **including everything you know**. Shortening the prose while keeping every point produces a dense wall that is harder to read, not easier.

So do not compress. **Cut whole points.** The test for each one:

> Would this detail change what the reader does next?

No → it does not go in the message. It stays available; you can answer if asked.

Corollary: never restate what the reader already has open. On a PR, the code is on screen. In a thread, the thread is above. In a ticket, the description is right there. Re-narrating it costs the reader time and tells them nothing.

## Default shape

1. The decision, finding, or ask — one sentence, first.
2. Why, if the reader could not infer it — one or two sentences.
3. Stop.

Do not add a closing summary, a restatement, or a sign-off.

## Cut these, always

- Rationale chains and the path you took to the answer ("I looked at X, then found Y, which led to Z")
- Alternatives you considered and rejected, unless the reader is being asked to weigh in on the choice
- Restating the diff, the file list, or what the code plainly shows
- Research, sourcing, or process narration — the reader wants the conclusion, not the method
- Test plans and verification narration where CI already reports it
- Preamble ("Just wanted to flag…"), and status ladders (`✅ Done`, `🚀 Shipped`)
- Stacked hedges. One calibration word is enough.

## Keep these

- The decision, finding, or ask
- Whatever the reader needs in order to **disagree** with you — if you cut the grounds for objection, you have not been concise, you have been evasive
- Anything genuinely not recoverable from the artifact the reader is looking at
- Non-obvious constraints, gotchas, or blast radius

## Short, not clipped

Concise means fewer points, not compressed writing. Write complete sentences. Spell out terms. No arrow chains (`A → B → fails`), no invented shorthand, no hyphen-stacked compounds. If forced to choose between short and clear, choose clear.

## Per surface

**PR description.** If the repo has its own PR template or `create-pr` guidance, that wins — follow it and apply the selection rule within it. Otherwise: the problem in one sentence, the fix in one sentence, and why it works in one or two. No bullet summary of files touched. No test plan section.

**PR review comment.** Three sentences is the default, six the ceiling. State what the code should do differently and why. A comment explaining a decision states the decision and the reason — not the investigation behind it. If a point needs more than six sentences, it is a conversation, not a comment: say the short version and offer to go deeper.

**Slack.** One short paragraph. Lead with what you need from them or what they need to know. No preamble. If it needs sections and headers, it is a doc — write the doc and link it.

**Linear / Notion comment.** Same as a PR comment. Ticket bodies carry more, but state the ask before the background.

**Commit message.** One short paragraph: what was wrong and the fix. No consequence chains, no `Result:` / `Symptom:` sections, no bullet list of every place the bug surfaced.

## Examples

**PR comment explaining a tentative choice**

BAD:
> I went with the token-bucket approach here rather than a sliding window. I looked at three options: a fixed window counter, which is simplest but allows a 2x burst at the boundary; a sliding window log, which is exact but needs per-request storage that grows with traffic; and a token bucket, which approximates well with O(1) state. Given that our traffic pattern shows bursts around the top of the hour, the boundary problem with fixed windows would have been a real issue in practice. The sliding window log would have worked but the memory profile concerned me at our current request volume, and it would have meant adding a Redis dependency we don't currently have in this service. So token bucket seemed like the best tradeoff, though I'm open to revisiting if we see accuracy problems.

GOOD:
> Token bucket rather than a sliding window, mainly to avoid adding a Redis dependency here. Tentative — happy to revisit if the accuracy is off.

**Slack message reporting a finding**

BAD:
> Hey! I wanted to give you an update on the investigation into the latency spike. I started by looking at the Datadog traces for the affected window and noticed that p99 was elevated across all endpoints, not just the ones we'd initially suspected. That pointed away from a specific code path, so I checked the RDS metrics next and found that read IOPS were saturated starting at 14:20 UTC. Digging into the query performance data, the culprit appears to be the new report export, which is doing a full table scan on `loan_events`. I think we should add an index, but wanted to check with you first.

GOOD:
> The latency spike is the new report export doing a full table scan on `loan_events` — saturated read IOPS from 14:20 UTC. Suggest adding an index; want me to?

Note what the good versions keep: the conclusion, and enough for the reader to push back. Both drop the investigation entirely.

## Before you post

Read the draft once and ask: what is the reader supposed to do after reading this? If a sentence does not serve that, delete it.

Then post it. Do not append the detail you just cut.
