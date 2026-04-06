## E2E Testing with Playwright

### Project layout

- Config: `apps/web/playwright.config.ts`
- Tests: `apps/web/e2e/`
- Page objects: `apps/web/e2e/pages/`
- Scenarios: `apps/web/e2e/scenarios/`
- Run tests: `pnpm test:e2e` (from root or `apps/web`)
- Tests use Chromium only by default
- `webServer` config auto-starts Vite dev; `reuseExistingServer: true` skips startup when the server is already running

### Page Object Model (required)

- Every view/page gets a page object in `e2e/pages/`
- Page objects extend `BasePage` from `./base.page`
- Expose domain-oriented actions only (e.g., `addTodo(title)`, not `clickButton()`)
- No assertions in page objects — assertions belong in test files
- Locator priority: `getByTestId` > `getByRole` > `getByPlaceholder` > `getByLabel` > `getByText` > CSS selectors
- Prefer `data-testid` attributes; flag missing test-ids as source code improvements

### Scenario files (`.scenario.md`)

Scenario files live in `e2e/scenarios/`. They are plain-text, UI-agnostic user task descriptions. Format: numbered steps describing what the user does and what they expect to see.

Example:

```
# Create a todo
1. Navigate to the app
2. Enter "Buy groceries" as a new todo
3. Submit the new todo
4. Verify "Buy groceries" appears in the todo list
```

Use `/author-e2e` to generate Playwright tests from scenario files.

### Smoke test guidelines

- The scaffolded smoke test is purely structural — page loads, heading visible
- No database-dependent assertions in smoke tests
- Smoke tests verify the app starts and basic navigation works

Also see `flakiness-practices.md` for reliability guidance.
