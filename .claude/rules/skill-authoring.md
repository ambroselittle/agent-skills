## Skill Authoring

- Do not set `disable-model-invocation: true` in SKILL.md frontmatter unless the user explicitly asks for it. It blocks the skill from being invoked via the Skill tool, which breaks orchestration (e.g., solve-take-home calling /create-repo). If you see it on an existing skill, ask before keeping it — the answer will almost always be to remove it.
