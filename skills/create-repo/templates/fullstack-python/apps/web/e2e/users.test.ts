import { expect, test } from "@playwright/test"

test.describe("user CRUD via REST API", () => {
  test("list users returns array", async ({ request }) => {
    const response = await request.get("/api/users/")
    expect(response.ok()).toBeTruthy()

    const users = await response.json()
    expect(Array.isArray(users)).toBeTruthy()
  })

  test("create and retrieve a user", async ({ request }) => {
    const uniqueEmail = `test-${Date.now()}@example.com`

    // Create
    const createResponse = await request.post("/api/users/", {
      data: { name: "Test User", email: uniqueEmail },
    })
    expect(createResponse.ok()).toBeTruthy()

    const created = await createResponse.json()
    expect(created.name).toBe("Test User")
    expect(created.email).toBe(uniqueEmail)
    expect(created.id).toBeDefined()

    // Retrieve
    const getResponse = await request.get(`/api/users/${created.id}`)
    expect(getResponse.ok()).toBeTruthy()

    const retrieved = await getResponse.json()
    expect(retrieved.name).toBe("Test User")
    expect(retrieved.email).toBe(uniqueEmail)
  })

  test("update a user", async ({ request }) => {
    const uniqueEmail = `update-${Date.now()}@example.com`

    const createResponse = await request.post("/api/users/", {
      data: { name: "Original", email: uniqueEmail },
    })
    const created = await createResponse.json()

    const updateResponse = await request.patch(`/api/users/${created.id}`, {
      data: { name: "Updated" },
    })
    expect(updateResponse.ok()).toBeTruthy()

    const updated = await updateResponse.json()
    expect(updated.name).toBe("Updated")
    expect(updated.email).toBe(uniqueEmail)
  })

  test("delete a user", async ({ request }) => {
    const uniqueEmail = `delete-${Date.now()}@example.com`

    const createResponse = await request.post("/api/users/", {
      data: { name: "ToDelete", email: uniqueEmail },
    })
    const created = await createResponse.json()

    const deleteResponse = await request.delete(`/api/users/${created.id}`)
    expect(deleteResponse.ok()).toBeTruthy()

    // Verify deleted
    const getResponse = await request.get(`/api/users/${created.id}`)
    expect(getResponse.status()).toBe(404)
  })
})
