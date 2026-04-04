import { readFileSync, writeFileSync, existsSync } from "fs"
import { execSync } from "child_process"
import { join } from "path"

const root = join(import.meta.dirname, "..")

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
const packageEnvs: Record<string, string[]> = {
  "packages/db": ["DATABASE_URL"],
  "apps/api": ["DATABASE_URL", "API_PORT"],
  "apps/web": ["WEB_PORT", "VITE_API_PORT"],
}

for (const [pkg, vars] of Object.entries(packageEnvs)) {
  const pkgDir = join(root, pkg)
  if (!existsSync(pkgDir)) continue
  const content = vars
    .filter((v) => ports[v] || process.env[v])
    .map((v) => `${v}=${ports[v] || process.env[v]}`)
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
