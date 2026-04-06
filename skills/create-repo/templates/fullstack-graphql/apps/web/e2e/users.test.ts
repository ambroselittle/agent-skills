import { test, expect } from "@playwright/test"

test.describe("user CRUD via GraphQL", () => {
  test("users query returns seeded users", async ({ request }) => {
    const response = await request.post("/api/graphql", {
      data: {
        query: "{ users { id email name } }",
      },
    })
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    const users = body.data.users
    expect(users.length).toBeGreaterThanOrEqual(2)

    const emails = users.map((u: { email: string }) => u.email)
    expect(emails).toContain("alice@example.com")
    expect(emails).toContain("bob@example.com")
  })

  test("createUser mutation adds a new user", async ({ request }) => {
    const uniqueEmail = `test-${Date.now()}@example.com`

    const response = await request.post("/api/graphql", {
      data: {
        query: `mutation CreateUser($email: String!, $name: String) {
          createUser(email: $email, name: $name) { id email name }
        }`,
        variables: { email: uniqueEmail, name: "Test User" },
      },
    })
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    const created = body.data.createUser
    expect(created.email).toBe(uniqueEmail)
    expect(created.name).toBe("Test User")

    // Verify user appears in list
    const listResponse = await request.post("/api/graphql", {
      data: {
        query: "{ users { email } }",
      },
    })
    const listBody = await listResponse.json()
    const emails = listBody.data.users.map((u: { email: string }) => u.email)
    expect(emails).toContain(uniqueEmail)
  })
})
