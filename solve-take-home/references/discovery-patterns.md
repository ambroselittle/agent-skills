# Discovery Patterns

Where to find instructions, requirements, and constraints in a take-home repo. Work through these in order — stop expanding your search once you have a complete picture of what to build.

## Primary Instruction Files

Check these first. Most take-homes put everything in one of these files. Look for each base name across common text formats: `.md`, `.txt`, `.html`, `.rst`, `.adoc` (e.g., `INSTRUCTIONS.md`, `INSTRUCTIONS.txt`, `INSTRUCTIONS.html`).

Base names, in priority order:

- `README` — most common location; instructions are often the entire readme
- `INSTRUCTIONS`
- `PROMPT`
- `CHALLENGE`
- `ASSIGNMENT`
- `REQUIREMENTS`
- `SPEC`
- `TODO`

Also check for bare files with no extension (e.g., just `INSTRUCTIONS`).

Read whichever exists. If multiple exist, read all — they may cover different aspects.

## Documentation Directories

- `docs/` — may contain detailed specs, API descriptions, or architecture diagrams
- PDFs in root or `docs/` — some companies deliver instructions as PDF attachments

PDFs are easy to miss. Glob for `*.pdf` early.

## Implicit Specifications

When prose instructions are thin, the code itself is the spec. These patterns define what to build:

- **Test files** — `__tests__/`, `tests/`, `test/`, `spec/`, `*.test.*`, `*.spec.*` — pre-written tests define exact input/output expectations that prose instructions leave ambiguous. Look for `test.todo()`, `@pytest.mark.skip`, `xit()`, or `pending` stubs — these are requirements in disguise.
- **Starter code with TODOs** — `// TODO: implement`, `# TODO`, `pass` placeholders, `raise NotImplementedError` — these mark exactly what needs building and where.
- **Type definitions and interfaces** — `.d.ts` files, protocol classes, abstract base classes, trait definitions — these define the contract your implementation must satisfy.

Test files are often the most precise specification in the repo. Prioritize them over ambiguous prose.

## Stack and Tooling Signals

These files reveal the prescribed stack, expected patterns, and what "passing" means:

- `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` — prescribed dependencies and language version
- `tsconfig.json` / `setup.cfg` / `ruff.toml` / `biome.json` — config choices hint at expected code style and patterns
- `.github/workflows/` / `.gitlab-ci.yml` / `Makefile` — CI config reveals what must pass (lint, typecheck, test suites, build)
- `docker-compose.yml` / `Dockerfile` — infrastructure the solution is expected to run in
- `.env.example` / `.env.sample` — environment variables the solution needs; copy to `.env` before starting

CI config is especially valuable — it tells you exactly what the evaluator will run. Match that.

## Submission Format Clues

Scan instructions for how to deliver the solution:

- Phrases: "PR", "pull request", "zip", "deploy", "hosted URL", "email submission"
- GitHub template repos often expect a PR back to the original
- Look for `SUBMISSION.md` or a submission section in the README

Knowing the submission format early prevents rework — a "deploy to Vercel" requirement changes how you structure the project.

## Time Constraint Signals

Scan instructions for time expectations:

- Phrases: "time limit", "hours", "complete within", "spend no more than"
- Usually in README or INSTRUCTIONS, sometimes in the email that accompanied the repo

Time constraints determine scope — a 2-hour limit means ship a working core, not a polished product.
