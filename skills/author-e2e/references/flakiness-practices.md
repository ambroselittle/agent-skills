<!-- Canonical copy also exists in create-repo templates: templates/common/.claude/rules/flakiness-practices.md — keep in sync -->

# Flakiness Practices Checklist

Every E2E test should be evaluated against these practices.

## Timing & Waiting

1. **Wait for data before interacting.** Dev servers may be slower than production. Assert that content is ready before interacting: `await expect(locator).toBeVisible()`. You don't need this for every interaction — just when changing page/tab context to ensure the view is ready.

2. **Use Playwright's auto-waiting.** Prefer `getByRole`, `getByTestId`, etc. over raw CSS selectors — Playwright auto-waits for these. Avoid `waitForTimeout()` or `page.waitForSelector()` when an assertion or locator wait suffices. NEVER use `networkidle` — rely on UI readiness indicators.

3. **Avoid hardcoded waits.** `await page.waitForTimeout(2000)` is almost always wrong. Wait for a specific condition instead. As a last resort, consider modifying source code to be more testable (add test-ids, loading states). This is commendable so long as UX remains good.

4. **Don't use `force: true` to paper over timing issues.** If you need `force`, the element isn't ready — fix the wait logic. Use `force` only for known Playwright quirks (intentionally overlapping elements).

5. **Don't assert on transient states.** Avoid asserting loading spinners appeared — they may resolve before the assertion runs. Assert the final state (data visible, spinner gone).

6. **Be careful with `click()` on elements that trigger navigation.** Use `await Promise.all([page.waitForURL(...), element.click()])` or assert the URL after click to avoid race conditions.

## Selectors & Matching

7. **Use `exact: true` for text matching.** `getByText("Save")` also matches "Save and close", "Unsaved changes", etc. Always pass `{ exact: true }` to avoid ambiguous matches.

8. **Prefer specific locator chains over broad queries.** Scope to a container: `page.getByTestId("todo-list").getByRole("button", { name: "Edit" })` beats `page.getByRole("button", { name: "Edit" }).first()`.

9. **Avoid `.first()`, `.last()`, `.nth()` on dynamic lists.** Index-dependent selectors break when order or content changes. Filter by text or test ID instead.

10. **Use `toBeVisible()` not `toHaveCount()` for presence checks.** `toBeVisible()` auto-retries; `toHaveCount(1)` can fail during re-renders when the element briefly doesn't exist.

## Test Isolation & Data

11. **Don't depend on element order or exact counts** unless that's what you're testing. Lists may load in different order.

12. **Handle notifications and modals.** Unexpected modals overlaying clickable elements cause flakes. Dismiss or close them before interacting with elements they may cover.

13. **Be mindful of parallelization.** Tests run in parallel. Tests modifying shared resources (creating/deleting entities) can interfere. Use unique names or operate on pre-seeded data.

## Testability Improvements

When a test is hard to write reliably, consider improving the source code:

- **Add `data-testid` attributes** to interactive elements that lack unique identifiers
- **Add loading/empty states** that tests can wait for
- **Ensure buttons are disabled** during async operations (prevents double-click flakes)
- **Use deterministic content** where possible (avoid timestamps, random IDs in displayed text)

These source changes are encouraged — they improve both testability and UX.
