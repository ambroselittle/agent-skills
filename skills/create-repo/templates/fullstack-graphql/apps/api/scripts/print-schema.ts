import { printSchema } from "graphql"
import { writeFileSync } from "node:fs"
import { schema } from "../src/schema"

writeFileSync("schema.graphql", `${printSchema(schema)}\n`)
console.log("Wrote schema.graphql")
