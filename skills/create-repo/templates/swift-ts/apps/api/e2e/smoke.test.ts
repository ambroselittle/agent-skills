import { test, expect } from "@playwright/test"

test.describe("smoke tests", () => {
  test("health endpoint responds", async ({ request }) => {
    const response = await request.get("/api/health")
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.status).toBe("ok")
  })
})
