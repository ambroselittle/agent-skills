import "dotenv/config"
import { PrismaPg } from "@prisma/adapter-pg"
import { PrismaClient } from "./generated/prisma/client"

// In production, RDS requires SSL but the pg adapter doesn't enable it by default.
// Passing ssl: { rejectUnauthorized: false } handles cases where the DATABASE_URL
// doesn't include sslmode params (e.g. local dev). No-op when SSL is not required.
const sslOptions =
  process.env.NODE_ENV === "production" ? { ssl: { rejectUnauthorized: false } } : {}
const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL, ...sslOptions })
export const db = new PrismaClient({ adapter })

export type { PrismaClient } from "./generated/prisma/client"
export * from "./generated/prisma/client"
