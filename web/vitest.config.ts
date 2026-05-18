import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/__tests__/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "server-only": path.resolve(__dirname, "test/server-only-stub.ts"),
      "@": path.resolve(__dirname, "."),
    },
  },
});
