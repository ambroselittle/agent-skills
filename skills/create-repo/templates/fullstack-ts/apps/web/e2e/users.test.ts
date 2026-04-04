import { test, expect } from "@playwright/test"

test.describe("user CRUD via tRPC", () => {
  test("user.list returns seeded users", async ({ request }) => {
    // tRPC batch GET for user.list procedure
    const response = await request.get("/api/trpc/user.list?batch=1&input=%7B%220%22%3A%7B%7D%7D")
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    const users = body[0].result.data
    expect(users.length).toBeGreaterThanOrEqual(2)

    const emails = users.map((u: { email: string }) => u.email)
    expect(emails).toContain("alice@example.com")
    expect(emails).toContain("bob@example.com")
  })

  test("user.create adds a new user", async ({ request }) => {
    const uniqueEmail = `test-${Date.now()}@example.com`

    // tRPC batch POST for user.create mutation
    const response = await request.post("/api/trpc/user.create?batch=1", {
      data: {
        "0": { email: uniqueEmail, name: "Test User" },
      },
    })
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    const created = body[0].result.data
    expect(created.email).toBe(uniqueEmail)
    expect(created.name).toBe("Test User")

    // Verify user appears in list
    const listResponse = await request.get("/api/trpc/user.list?batch=1&input=%7B%220%22%3A%7B%7D%7D")
    const listBody = await listResponse.json()
    const emails = listBody[0].result.data.map((u: { email: string }) => u.email)
    expect(emails).toContain(uniqueEmail)
  })
})
