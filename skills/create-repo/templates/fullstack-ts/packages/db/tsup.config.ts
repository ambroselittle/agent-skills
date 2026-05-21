import { defineConfig } from "tsup"

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  dts: false,
  platform: "node",
  // Keep Prisma and pg as external — they must be loaded from node_modules at runtime
  external: ["@prisma/client", "@prisma/adapter-pg", "pg"],
})
