import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["src/pruebas/preparar.ts"],
    unstubGlobals: true,
    // Sin caché de módulos en disco: guardaba el resultado de import.meta.glob y
    // sin-almacenamiento.test.ts dejaba de revisar los archivos nuevos.
    fsModuleCache: false,
  },
});
