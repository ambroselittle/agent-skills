## Skill Authoring

- Do not set `disable-model-invocation: true` in SKILL.md frontmatter unless the user explicitly asks for it. It blocks the skill from being invoked via the Skill tool, which breaks orchestration (e.g., solve-take-home calling /create-repo). If you see it on an existing skill, ask before keeping it — the answer will almost always be to remove it.
- **Use context scripts for pre-loaded data.** When a skill needs data available at load time (before AI runs), use the `!` backtick pattern with a context script: `!~/.claude/skills/<skill>/scripts/context.sh <flag>`. Never use `cd && ...` compound commands in `!` backticks — they get blocked by permission checks. Wrap the logic in a context script instead.
- **Deterministic work should be scripts, not AI.** If a step has no judgment calls (file I/O, shell commands, version lookups), make it a Python or shell script. The AI should only handle interview questions, diagnostics, and customizations.
- **`AskUserQuestion` hard constraints (from schema):**
  - `questions`: 1–4 per call (minItems: 1, maxItems: 4)
  - `options`: exactly 2–4 per question (minItems: 2, maxItems: 4) — the tool auto-appends an "Other / type something different" entry; never add your own
  - `header`: max 12 characters
  - `label`: 1–5 words; `description`: explains the choice
  - `multiSelect`: boolean, default false
  - `preview`: only supported on single-select questions; renders a monospace markdown box for side-by-side comparison (good for code/layout mockups)
  - Put the recommended/default option **first** — the UI selects it by default. Add `"(Recommended)"` to the label when you want to be explicit.
  - **Never construct options from dynamic data without a ≥2 count guard.** If a data source (Dockerfiles found, derived names) yields only 1 item, either skip the question entirely or pad to 2 with a sensible alternative.
  - **No iterative loops inside a batch.** All questions in one call are presented simultaneously and answers come back together. If question B's options depend on question A's answer, they must be separate `AskUserQuestion` calls — sequential, not batched.
