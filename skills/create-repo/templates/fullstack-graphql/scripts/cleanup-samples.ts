import { readFileSync, writeFileSync } from "node:fs"
import { execSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, "..")

const SENTINEL_RE = /\/\/\s*---\s*sample \w+ start\s*---[\s\S]*?\/\/\s*---\s*sample \w+ end\s*---\n?/g

const targets = [
  "packages/db/prisma/schema.prisma",
  "apps/api/src/schema.ts",
  "packages/db/prisma/seed.ts",
]

let removedCount = 0
for (const rel of targets) {
  const path = join(root, rel)
  try {
    const content = readFileSync(path, "utf-8")
    const cleaned = content.replace(SENTINEL_RE, "")
    if (cleaned !== content) {
      writeFileSync(path, cleaned)
      removedCount++
      console.log(`Cleaned: ${rel}`)
    }
  } catch {
    // File doesn't exist — skip
  }
}

if (removedCount > 0) {
  console.log("\nRegenerating Prisma client...")
  execSync("pnpm --filter @*/db exec prisma generate", { cwd: root, stdio: "inherit" })
  console.log("Formatting...")
  execSync("npx biome check --write .", { cwd: root, stdio: "inherit" })
  console.log(`\nDone — removed sample content from ${removedCount} file(s).`)
} else {
  console.log("No sample content found — nothing to clean up.")
}
