import getPort from "get-port"
import { existsSync, mkdirSync, openSync, readFileSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const REGISTRY_DIR = join(homedir(), ".agent-skills")
const REGISTRY_PATH = join(REGISTRY_DIR, ".port-registry.json")
const LOCK_PATH = join(REGISTRY_DIR, ".port-registry.lock")

interface PortEntry {
  DB_PORT?: number
  API_PORT?: number
  WEB_PORT?: number
  dir: string
  updated: string
}
type Registry = Record<string, PortEntry>

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function acquireLock(): Promise<() => void> {
  mkdirSync(REGISTRY_DIR, { recursive: true })
  const deadline = Date.now() + 10_000
  while (true) {
    try {
      openSync(LOCK_PATH, "wx")
      return () => {
        try {
          unlinkSync(LOCK_PATH)
        } catch {}
      }
    } catch (e: unknown) {
      const err = e as NodeJS.ErrnoException
      if (err.code !== "EEXIST") throw e
      // Remove lock if stale (> 30s old)
      try {
        if (Date.now() - statSync(LOCK_PATH).mtimeMs > 30_000) {
          unlinkSync(LOCK_PATH)
          continue
        }
      } catch {}
      if (Date.now() > deadline) {
        try {
          unlinkSync(LOCK_PATH)
        } catch {}
        openSync(LOCK_PATH, "wx")
        return () => {
          try {
            unlinkSync(LOCK_PATH)
          } catch {}
        }
      }
      await sleep(50)
    }
  }
}

function readRegistry(): Registry {
  try {
    return JSON.parse(readFileSync(REGISTRY_PATH, "utf-8")) as Registry
  } catch {
    return {}
  }
}

function cleanRegistry(registry: Registry): Registry {
  return Object.fromEntries(Object.entries(registry).filter(([, entry]) => existsSync(entry.dir)))
}

function takenPorts(registry: Registry): Set<number> {
  const ports = new Set<number>()
  for (const entry of Object.values(registry)) {
    if (entry.DB_PORT) ports.add(entry.DB_PORT)
    if (entry.API_PORT) ports.add(entry.API_PORT)
    if (entry.WEB_PORT) ports.add(entry.WEB_PORT)
  }
  return ports
}

async function findFreePort(start: number, end: number, exclude: Set<number>): Promise<number> {
  const candidates = Array.from({ length: end - start + 1 }, (_, i) => start + i).filter(
    (p) => !exclude.has(p),
  )
  return getPort({ port: candidates as [number, ...number[]] })
}

async function main() {
  const root = process.cwd()
  const projectName = (() => {
    try {
      const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf-8")) as { name?: string }
      return (pkg.name ?? "app").replace(/^@/, "").replace("/", "-")
    } catch {
      return "app"
    }
  })()

  const release = await acquireLock()
  try {
    const registry = cleanRegistry(readRegistry())
    const taken = takenPorts(registry)

    const WEB_PORT = await findFreePort(3000, 3099, taken)
    taken.add(WEB_PORT)
    const API_PORT = await findFreePort(3100, 3199, taken)
    taken.add(API_PORT)
    const DB_PORT = await findFreePort(5432, 5499, taken)
    taken.add(DB_PORT)

    registry[projectName] = { WEB_PORT, API_PORT, DB_PORT, dir: root, updated: new Date().toISOString() }
    writeFileSync(REGISTRY_PATH, `${JSON.stringify(registry, null, 2)}\n`)

    const dbName =
      (process.env.npm_package_name?.replace(/^@/, "").replace("/", "-")) ?? projectName
    const DATABASE_URL = `postgresql://postgres:postgres@localhost:${DB_PORT}/${dbName}_dev`

    const envContent = [
      `WEB_PORT=${WEB_PORT}`,
      `API_PORT=${API_PORT}`,
      `DB_PORT=${DB_PORT}`,
      `DATABASE_URL=${DATABASE_URL}`,
    ].join("\n")

    writeFileSync(".env.ports", `${envContent}\n`)
    console.log("Ports written to .env.ports:", { WEB_PORT, API_PORT, DB_PORT, DATABASE_URL })
  } finally {
    release()
  }
}

main()
