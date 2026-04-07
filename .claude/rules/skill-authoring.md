## Skill Authoring

- Do not set `disable-model-invocation: true` in SKILL.md frontmatter unless the user explicitly asks for it. It blocks the skill from being invoked via the Skill tool, which breaks orchestration (e.g., solve-take-home calling /create-repo). If you see it on an existing skill, ask before keeping it — the answer will almost always be to remove it.
- **Use context scripts for pre-loaded data.** When a skill needs data available at load time (before AI runs), use the `!` backtick pattern with a context script: `!~/.claude/skills/<skill>/scripts/context.sh <flag>`. Never use `cd && ...` compound commands in `!` backticks — they get blocked by permission checks. Wrap the logic in a context script instead.
- **Deterministic work should be scripts, not AI.** If a step has no judgment calls (file I/O, shell commands, version lookups), make it a Python or shell script. The AI should only handle interview questions, diagnostics, and customizations.
