import { test, expect } from "@playwright/test"

test.describe("user REST API", () => {
  test("GET /api/users returns seeded users", async ({ request }) => {
    const response = await request.get("/api/users")
    expect(response.ok()).toBeTruthy()

    const users = await response.json()
    expect(users.length).toBeGreaterThanOrEqual(2)

    const emails = users.map((u: { email: string }) => u.email)
    expect(emails).toContain("alice@example.com")
    expect(emails).toContain("bob@example.com")
  })

  test("POST /api/users creates a new user", async ({ request }) => {
    const uniqueEmail = `test-${Date.now()}@example.com`

    const response = await request.post("/api/users", {
      data: { email: uniqueEmail, name: "Test User" },
    })
    expect(response.ok()).toBeTruthy()

    const created = await response.json()
    expect(created.email).toBe(uniqueEmail)
    expect(created.name).toBe("Test User")

    // Verify user appears in list
    const listResponse = await request.get("/api/users")
    const users = await listResponse.json()
    const emails = users.map((u: { email: string }) => u.email)
    expect(emails).toContain(uniqueEmail)
  })
})
