// Ningún dato del peticionario se guarda en el navegador ni sale por la consola:
// el código de la interfaz no usa el almacenamiento del navegador ni la consola.
import { describe, expect, test } from "vitest";

const fuentes = import.meta.glob<string>(["../**/*.{ts,tsx}", "!../pruebas/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const PROHIBIDO = /\b(localStorage|sessionStorage|indexedDB|caches|document\.cookie|console)\b/;

describe("código de la interfaz", () => {
  test("hay archivos que revisar", () => {
    expect(Object.keys(fuentes)).toContain("../main.tsx");
  });

  test.each(Object.entries(fuentes))("%s no usa almacenamiento ni consola", (_ruta, texto) => {
    expect(texto).not.toMatch(PROHIBIDO);
  });
});
