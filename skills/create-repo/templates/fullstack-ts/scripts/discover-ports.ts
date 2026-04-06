import getPort, { portNumbers } from "get-port"
import { writeFileSync } from "node:fs"

async function main() {
  const ports = {
    WEB_PORT: await getPort({ port: portNumbers(3000, 3099) }),
    API_PORT: await getPort({ port: portNumbers(3100, 3199) }),
    DB_PORT: await getPort({ port: portNumbers(5432, 5499) }),
  }

  const dbName = process.env.npm_package_name?.replace(/^@/, "").replace(/\//, "-") || "app"
  const DATABASE_URL = `postgresql://postgres:postgres@localhost:${ports.DB_PORT}/${dbName}_dev`

  const envContent = [
    ...Object.entries(ports).map(([k, v]) => `${k}=${v}`),
    `DATABASE_URL=${DATABASE_URL}`,
  ].join("\n")

  writeFileSync(".env.ports", `${envContent}\n`)
  console.log("Ports written to .env.ports:", { ...ports, DATABASE_URL })
}

main()
