# Agent Skills

General-purpose engineering workflow skills for AI coding agents, following the [Agent Skills](https://agentskills.io) open standard.

## Skills

| Skill | Description |
| --- | --- |
| **start-work** | Plan work before writing code. Takes a GitHub issue or description, discovers relevant code, and produces a phased implementation plan. |
| **plan-review** | Review an implementation plan with parallel specialized agents (architecture, completeness, security, testing strategy). |
| **hack** | Implement work from a plan, phase by phase. Coordinates parallel agents, verifies, and commits per task. Supports full auto mode. |
| **code-review** | Multi-pass parallel code review with specialized agents. Two-pass approach (normal + reversed diff) for higher recall. Posts findings to PR. |
| **ship** | Verify, commit, push, and open a PR. Runs a docs sanity check before pushing. Fills the repo's PR template. |
| **learn** | Route lessons from a work item to skill updates, repo-local rules, or user memory. |
| **fix-tests** | Diagnose and fix CI test failures. Finds failing tests, groups by root cause, and fixes methodically. |
| **create-repo** | Bootstrap a new monorepo from a template (fullstack-ts, fullstack-graphql, fullstack-python, api-ts, api-python, swift-ts). Resolves current versions, scaffolds, verifies, and commits. |
| **solve-take-home** | Solve a coding take-home challenge end-to-end. Discovers instructions, scaffolds if needed, plans, implements, polishes against evaluation criteria, and ships. |
| **make-skill** | Create a new agent skill through an interactive interview process. |

## Workflow

The core skills form a pipeline:

```
/start-work → /plan-review (optional) → /hack → /ship → /code-review → /learn
```

## Setup

Run `setup.sh` to symlink skills and shared resources into `~/.claude/skills/`:

```bash
./setup.sh
```

This creates symlinks so skills stay in sync with the repo — no need to re-run after edits.

## License

[MIT](LICENSE)
