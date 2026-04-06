import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { execSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, "..")

// 1. Discover ports
console.log("Discovering free ports...")
execSync("tsx scripts/discover-ports.ts", { cwd: root, stdio: "inherit" })

// 2. Read discovered ports
const portsEnv = readFileSync(join(root, ".env.ports"), "utf-8")
const ports: Record<string, string> = {}
for (const line of portsEnv.split("\n")) {
  const [k, v] = line.split("=")
  if (k && v) ports[k] = v
}

// 3. Read base .env.example
const example = existsSync(join(root, ".env.example"))
  ? readFileSync(join(root, ".env.example"), "utf-8")
  : ""

// 4. Build root .env (ports override example values)
const rootEnv = [
  example.trim(),
  "",
  "# Discovered ports (regenerate with: pnpm update-ports)",
  portsEnv.trim(),
  "",
  "# Docker isolation",
  `COMPOSE_PROJECT_NAME=${projectSlug()}-${worktreeSlug()}`,
].join("\n")

writeFileSync(join(root, ".env"), rootEnv + "\n")

// 5. Generate per-package .env files
// Keys are env var names to write; values are the source key from ports.
const packageEnvs: Record<string, Record<string, string>> = {
  "packages/db": { DATABASE_URL: "DATABASE_URL" },
  "apps/api": { DATABASE_URL: "DATABASE_URL", PORT: "API_PORT" },
  "apps/web": { WEB_PORT: "WEB_PORT", VITE_API_PORT: "API_PORT" },
}

for (const [pkg, varMap] of Object.entries(packageEnvs)) {
  const pkgDir = join(root, pkg)
  if (!existsSync(pkgDir)) continue
  const content = Object.entries(varMap)
    .filter(([, src]) => ports[src])
    .map(([dest, src]) => `${dest}=${ports[src]}`)
    .join("\n")
  writeFileSync(join(pkgDir, ".env"), content + "\n")
  console.log(`Wrote ${pkg}/.env`)
}

function projectSlug(): string {
  try {
    const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf-8"))
    return (pkg.name || "app").replace(/^@/, "").replace(/\//, "-")
  } catch {
    return "app"
  }
}

function worktreeSlug(): string {
  try {
    const gitDir = execSync("git rev-parse --git-dir", { cwd: root, encoding: "utf-8" }).trim()
    if (gitDir.includes("worktrees/")) {
      return gitDir.split("worktrees/").pop()?.split("/")[0] || "main"
    }
    return "main"
  } catch {
    return "main"
  }
}

console.log("\nSetup complete. Run `pnpm dev` to start.")
