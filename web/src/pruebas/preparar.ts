// Se carga antes de cada archivo de pruebas (vite.config.ts).
import { afterEach, beforeEach, expect, vi } from "vitest";

// React solo procesa act() si el entorno lo declara.
declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const METODOS = ["log", "info", "warn", "error", "debug"] as const;

// La interfaz nunca escribe en la consola: tampoco las advertencias de React.
beforeEach(() => {
  for (const metodo of METODOS) vi.spyOn(console, metodo);
});

afterEach(() => {
  for (const metodo of METODOS) expect(console[metodo]).not.toHaveBeenCalled();
  document.body.innerHTML = "";
  window.location.hash = "";
});
