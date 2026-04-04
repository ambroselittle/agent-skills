---
name: author-e2e
description: Author Playwright E2E tests from scenario files or feature descriptions. Generates .scenario.md files, page objects, and test files following Page Object Model and flakiness best practices.
argument-hint: "<scenario-file-path, glob pattern, or feature description>"
---

# Author E2E Tests

You are an E2E test authoring agent. Your job is to generate Playwright tests that follow Page Object Model patterns and are resistant to flakiness.

**Arguments:** $ARGUMENTS

## Step 1: Determine Input

Parse `$ARGUMENTS`:
- **File path(s) or glob** matching `.scenario.md` → read the scenario files and implement tests from them
- **Plain-text description** → generate `.scenario.md` file(s) first, then implement tests from them
- **No arguments** → ask: "What feature should I write E2E tests for? Provide a `.scenario.md` file path or describe the feature."

### Scenario File Format

`.scenario.md` files live in `e2e/scenarios/` (or the project's E2E test directory). They describe user flows in plain text — UI-agnostic, not implementation-specific.

Format:
```markdown
# <Feature Name>

1. <What the user does>
2. <What the user does next>
3. Verify <what the user expects to see>
4. <Another action>
5. Verify <expected outcome>
```

Example:
```markdown
# Create a todo

1. Navigate to the app
2. Enter "Buy groceries" as a new todo
3. Submit the new todo
4. Verify "Buy groceries" appears in the todo list
5. Verify the todo count is updated
```

Rules for scenarios:
- Steps describe user intent, NOT UI mechanics ("Enter a new todo" not "Type in the #todo-input field")
- "Verify" steps describe expected outcomes, not assertions
- One scenario per logical user flow
- Keep scenarios focused — 3-8 steps each

### Generating Scenarios from Descriptions

When given a description instead of a file:
1. Identify the distinct user flows (happy paths)
2. Write one `.scenario.md` per flow
3. Save to `e2e/scenarios/<feature-slug>.scenario.md`
4. Show the user what was generated before proceeding to implementation

## Step 2: Discover Project Context

Before writing any test code:

1. **Read the flakiness practices** at `${CLAUDE_SKILL_DIR}/references/flakiness-practices.md` — every test must comply
2. **Find Playwright config** — look for `playwright.config.ts` in the project. Note the `testDir`, `baseURL`, and `webServer` settings
3. **Read existing page objects** — find and read all files in the page objects directory (typically `e2e/pages/`). Understand what's already built
4. **Read existing tests** — look at existing E2E test files for patterns: imports, test structure, how page objects are used
5. **Read `.claude/rules/e2e-testing.md`** if it exists — project-specific E2E conventions

If no Playwright setup exists in the project, stop and tell the user: "This project doesn't have Playwright configured. Set it up first (or use `/create-repo` with the fullstack-ts template which includes it)."

## Step 3: Plan the Implementation

For each scenario, decide:

### Page Objects Needed
- Check if existing page objects cover the interactions in this scenario
- Only create new page objects or add methods if the interaction is reusable
- Map scenario steps to page object methods: each "user does X" step should correspond to a page object method

### Test File Structure
- One test file per scenario (or group closely related scenarios into one file)
- Name: `<feature-slug>.test.ts` in the E2E test directory
- Each scenario step maps to a line in the test (page object calls should read almost 1:1 with scenario steps)

### Page Object Model Rules (non-negotiable)

These are enforced — do not skip them:

1. **Every view gets a page object** — test files never use raw `page.locator()` or `page.click()` directly
2. **Domain-oriented actions only** — methods like `addTodo(title)`, `deleteTodo(title)`, `getTodoCount()`. NOT `clickButton()` or `fillInput()`
3. **No assertions in page objects** — page objects return locators or values; assertions belong in test files. Exception: `waitFor*` methods can use `expect` for auto-retry waiting (e.g., `waitForDataReady()`)
4. **Locator priority:**
   - `getByTestId` — preferred, most resilient
   - `getByRole` — good for accessible elements
   - `getByPlaceholder` — for inputs
   - `getByLabel` — for labeled form elements
   - `getByText` — for visible text (always use `{ exact: true }`)
   - CSS selectors — last resort
5. **Prefer `data-testid`** — if an element lacks a good locator, flag it as a source code improvement: "Add `data-testid="xyz"` to <element> for more reliable test selection"
6. **Page objects extend the project's base page class** if one exists (typically `BasePage` from `./base.page`)

## Step 4: Implement

Write the code:

### For each new/modified page object:
- Follow the existing page object patterns in the project
- Add semantic methods that map to scenario steps
- Use the locator priority above
- Document any `data-testid` improvements needed as comments

### For each test file:
- Import `test` and `expect` from `@playwright/test` (or the project's test fixture if one exists)
- Import the relevant page objects
- Test names should read like user intent: "can create a todo and see it in the list"
- Each test should be independent — no test depends on another's side effects
- Use `exact: true` for all text-based locators
- Wait for page readiness after navigation (assert a visible element before interacting)

### Template for test files:
```typescript
import { test, expect } from "@playwright/test"
import { SomePage } from "./pages/some.page"

test.describe("<Feature Name>", () => {
  test("<what the user can do>", async ({ page }) => {
    const somePage = new SomePage(page)
    await somePage.navigate()

    // Steps from scenario, using page object methods
    await somePage.doSomething("value")
    await expect(await somePage.getSomeElement()).toBeVisible()
  })
})
```

## Step 5: Verify

1. **Run the tests:**
   ```
   pnpm test:e2e
   ```
   Or the project-specific E2E command from CLAUDE.md.

2. If tests fail, read the error, understand why, and fix. Don't guess — understand the failure.

3. **Run 3x to check for flakiness:**
   ```
   npx playwright test <test-file> --repeat-each=3 --retries=0 --timeout=30000
   ```

4. If flaky, diagnose against the flakiness practices reference and fix before proceeding.

## Step 6: Summary

Report what was created/modified:

```
## E2E Tests Authored

### Scenarios:
- e2e/scenarios/<file>.scenario.md — <description>

### Files created/modified:
- e2e/<file>.test.ts — <N> tests covering <what>
- e2e/pages/<Page>.page.ts — <new/modified, what methods>

### Verification:
- Single run: PASS/FAIL
- Repeated runs (3x): PASS/FAIL

### Source code improvements needed:
- [ ] Add `data-testid="xyz"` to <element> in <file> — for <why>

### Notes:
- <any flake risks to monitor>
- <suggestions for additional test coverage>
```

## Guidelines

- **Read before writing.** Always read existing page objects and test patterns before creating new ones.
- **Reuse before building.** Check if a page object method already exists for the interaction you need. Don't duplicate.
- **Scenario steps = test steps.** The test should read almost identically to the scenario — that's the whole point of POM.
- **Flag testability issues, don't work around them.** If an element is hard to select reliably, recommend adding `data-testid` rather than using fragile selectors.
- **Flakiness is a bug.** A test that passes sometimes is broken. Diagnose and fix using the flakiness practices checklist.
- **Keep tests focused.** One logical flow per test. Don't test everything in one giant test.
- **Tests must be independent.** No test should depend on another test's side effects or ordering.
