import { describe, expect, test } from "vitest";
import { App } from "../App";
import { montar, respuestaJson, simularFetch } from "./ayudantes";

const AVISO = "Demostración con datos sintéticos: no ingrese datos personales reales";

function aviso(pantalla: HTMLElement): string | null {
  return pantalla.querySelector('[role="note"]')?.textContent?.trim() ?? null;
}

describe("aviso de datos sintéticos", () => {
  test("se ve en el registro", async () => {
    const pantalla = await montar(<App />);

    expect(pantalla.querySelector("h2")?.textContent).toContain("Registrar");
    expect(aviso(pantalla)).toBe(AVISO);
  });

  test("se ve en la bandeja", async () => {
    simularFetch(respuestaJson(200, { pagina: 1, total: 0, elementos: [] }));
    window.location.hash = "#bandeja";

    const pantalla = await montar(<App />);

    expect(pantalla.querySelector("h2")?.textContent).toContain("Bandeja");
    expect(aviso(pantalla)).toBe(AVISO);
  });
});
