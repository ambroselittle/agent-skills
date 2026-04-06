import type { CodegenConfig } from "@graphql-codegen/cli"

const config: CodegenConfig = {
  overwrite: true,
  schema: "../api/schema.graphql",
  documents: ["src/**/*.graphql"],
  generates: {
    "./src/generated/types.ts": {
      plugins: ["typescript"],
    },
    "./src/generated/schema.json": {
      plugins: ["introspection"],
    },
    "src/": {
      preset: "near-operation-file",
      presetConfig: {
        extension: ".generated.ts",
        baseTypesPath: "generated/types.ts",
      },
      plugins: ["typescript-operations", "typed-document-node"],
    },
  },
}

export default config
