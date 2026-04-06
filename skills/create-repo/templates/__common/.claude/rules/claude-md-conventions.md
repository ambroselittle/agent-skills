## CLAUDE.md vs .claude/rules/

- **CLAUDE.md** is orientation — what the project is, structure, how to build/test, what lives where
- **.claude/rules/** is behavioral directives — what to do or not do when working in this codebase
- Rules are either unscoped (always loaded) or path-scoped via `paths` frontmatter (loaded on demand)
- Keep CLAUDE.md concise and factual; put actionable rules in .claude/rules/
