import { test, expect } from "@playwright/test"

test.describe("smoke tests", () => {
  test("health endpoint responds", async ({ request }) => {
    const response = await request.get("/api/health")
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.status).toBe("ok")
  })

  test("tRPC health query resolves", async ({ request }) => {
    const response = await request.get("/api/trpc/health?batch=1&input=%7B%220%22%3A%7B%7D%7D")
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body[0].result.data.status).toBe("ok")
  })
})
