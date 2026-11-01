import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["src/pruebas/preparar.ts"],
    unstubGlobals: true,
  },
});
