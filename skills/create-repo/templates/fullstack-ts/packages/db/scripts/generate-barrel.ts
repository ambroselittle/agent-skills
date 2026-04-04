import { readdirSync, writeFileSync } from "fs"
import { join } from "path"

const dir = join("src", "generated", "prisma", "client")
const exports = readdirSync(dir)
  .filter((f) => f.endsWith(".ts") && f !== "index.ts")
  .map((f) => `export * from "./${f.replace(".ts", "")}"`)
  .join("\n")

writeFileSync(join(dir, "index.ts"), exports + "\n")
