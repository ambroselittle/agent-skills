import type { CodegenConfig } from "@graphql-codegen/cli"

const config: CodegenConfig = {
  schema: "../api/schema.graphql",
  documents: ["src/**/*.tsx", "src/**/*.ts", "!src/generated/**"],
  ignoreNoDocuments: true,
  generates: {
    "./src/generated/gql/": {
      preset: "client",
    },
  },
}

export default config
