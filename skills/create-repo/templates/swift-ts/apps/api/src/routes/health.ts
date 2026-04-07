import { OpenAPIHono, createRoute, z } from "@hono/zod-openapi"

const health = new OpenAPIHono()

const HealthResponseSchema = z.object({ status: z.string() }).openapi("HealthResponse")

const healthRoute = createRoute({
  method: "get",
  path: "/",
  responses: {
    200: {
      content: {
        "application/json": {
          schema: HealthResponseSchema,
        },
      },
      description: "Service health status",
    },
  },
})

health.openapi(healthRoute, (c) => c.json({ status: "ok" }))

export { health }
