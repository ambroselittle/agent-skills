import { test, expect } from "@playwright/test"

test.describe("smoke tests", () => {
  test("health endpoint responds", async ({ request }) => {
    const response = await request.get("/api/health")
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.status).toBe("ok")
  })

  test("openapi spec is served and valid", async ({ request }) => {
    const response = await request.get("/api/openapi.json")
    expect(response.ok()).toBeTruthy()

    const spec = await response.json()
    expect(spec.openapi).toBe("3.0.0")
    expect(spec.info.title).toBeTruthy()
    expect(spec.paths).toBeTruthy()

    // All sample routes are documented (paths include the /api prefix)
    expect(spec.paths["/api/health"]).toBeTruthy()
    expect(spec.paths["/api/users"]).toBeTruthy()

    // User schema is defined (needed for Swift OpenAPI Generator to produce typed models)
    expect(spec.components?.schemas?.User).toBeTruthy()
    expect(spec.components?.schemas?.CreateUser).toBeTruthy()
  })
})
