import { describe, expect, test } from "vitest";
import { act } from "react";
import { App } from "../App";
import { Bandeja } from "../Bandeja";
import type { PaginaPqrs, PqrsResumen, Semaforo } from "../tipos";
import { boton, campo, escribir, montar, pulsar, respuestaJson, simularFetch } from "./ayudantes";

function fila(id: number, semaforo: Semaforo, horasRestantes: number): PqrsResumen {
  return {
    id,
    radicado: `RAD-2026-${String(id).padStart(6, "0")}`,
    tipo: "RECLAMO",
    nivelRiesgo: "VITAL",
    area: { id: 2, nombre: "Urgencias" },
    estado: "REQUIERE_REVISION",
    vencimiento: {
      fecha: "2026-10-31T16:00:00-05:00",
      regla: "Reclamo en salud, riesgo vital: 24 horas corridas",
      semaforo,
      horasRestantes,
    },
  };
}

function pagina(numero: number, total: number, elementos: PqrsResumen[]): PaginaPqrs {
  return { pagina: numero, total, elementos };
}

function urls(fetch: ReturnType<typeof simularFetch>): string[] {
  return fetch.mock.calls.map(([url]) => String(url));
}

function radicados(pantalla: HTMLElement): string[] {
  return [...pantalla.querySelectorAll("tbody th")].map((celda) => celda.textContent ?? "");
}

describe("bandeja", () => {
  test("pide la primera página con el tamaño por defecto y muestra las filas en el orden de la API", async () => {
    // Un orden que la interfaz no produciría si ordenara por su cuenta.
    const elementos = [fila(3, "VERDE", 200.5), fila(1, "ROJO", -12.3), fila(2, "AMARILLO", 10.0)];
    const fetch = simularFetch(respuestaJson(200, pagina(1, 3, elementos)));

    const pantalla = await montar(<Bandeja />);

    expect(urls(fetch)).toEqual(["/api/v1/pqrs?pagina=1&tamano=20"]);
    expect(radicados(pantalla)).toEqual(["RAD-2026-000003", "RAD-2026-000001", "RAD-2026-000002"]);
    const colores = [...pantalla.querySelectorAll("tbody .semaforo")].map((s) => s.textContent);
    expect(colores).toEqual(["Verde", "Rojo", "Amarillo"]);
    const filas = [...pantalla.querySelectorAll("tbody tr")].map((f) => f.textContent ?? "");
    expect(filas[1]).toContain("-12,3 h");
    expect(filas[1]).toContain("Urgencias (2)");
    expect(filas[1]).toContain("Reclamo en salud, riesgo vital: 24 horas corridas");
  });

  test("envía los filtros con los nombres de la API y vuelve a la página 1", async () => {
    const fetch = simularFetch(
      respuestaJson(200, pagina(1, 0, [])),
      respuestaJson(200, pagina(1, 1, [fila(1, "ROJO", -1.0)])),
    );
    const pantalla = await montar(<Bandeja />);

    await escribir(campo(pantalla, "Semáforo"), "ROJO");
    await escribir(campo(pantalla, "Estado"), "REQUIERE_REVISION");
    await escribir(campo(pantalla, "Tipo"), "RECLAMO");
    await escribir(campo(pantalla, "Área sugerida"), "4");
    await escribir(campo(pantalla, "Por página"), "50");
    await pulsar(boton(pantalla, "Aplicar"));

    expect(urls(fetch)[1]).toBe(
      "/api/v1/pqrs?semaforo=ROJO&estado=REQUIERE_REVISION&tipo=RECLAMO&idArea=4&pagina=1&tamano=50",
    );
    expect(radicados(pantalla)).toEqual(["RAD-2026-000001"]);
  });

  test("pagina con Anterior y Siguiente, y Aplicar vuelve a la primera", async () => {
    const fetch = simularFetch(
      respuestaJson(200, pagina(1, 45, [fila(1, "ROJO", -5.0)])),
      respuestaJson(200, pagina(2, 45, [fila(21, "AMARILLO", 3.0)])),
      respuestaJson(200, pagina(3, 45, [fila(41, "VERDE", 90.0)])),
      respuestaJson(200, pagina(2, 45, [fila(21, "AMARILLO", 3.0)])),
      respuestaJson(200, pagina(1, 45, [fila(1, "ROJO", -5.0)])),
    );
    const pantalla = await montar(<Bandeja />);
    expect(pantalla.textContent).toContain("Página 1 de 3");
    expect(boton(pantalla, "Anterior").disabled).toBe(true);

    await pulsar(boton(pantalla, "Siguiente"));
    await pulsar(boton(pantalla, "Siguiente"));
    expect(pantalla.textContent).toContain("Página 3 de 3");
    expect(boton(pantalla, "Siguiente").disabled).toBe(true);

    await pulsar(boton(pantalla, "Anterior"));
    await pulsar(boton(pantalla, "Aplicar"));

    expect(urls(fetch)).toEqual([
      "/api/v1/pqrs?pagina=1&tamano=20",
      "/api/v1/pqrs?pagina=2&tamano=20",
      "/api/v1/pqrs?pagina=3&tamano=20",
      "/api/v1/pqrs?pagina=2&tamano=20",
      "/api/v1/pqrs?pagina=1&tamano=20",
    ]);
  });

  test("Actualizar repite la misma consulta", async () => {
    const fetch = simularFetch(respuestaJson(200, pagina(1, 0, [])), respuestaJson(200, pagina(1, 0, [])));
    const pantalla = await montar(<Bandeja />);

    await pulsar(boton(pantalla, "Actualizar"));

    expect(urls(fetch)).toEqual(["/api/v1/pqrs?pagina=1&tamano=20", "/api/v1/pqrs?pagina=1&tamano=20"]);
    expect(pantalla.textContent).toContain("No hay PQRS con estos filtros.");
  });

  test("muestra el 400 de un filtro inválido con su campo", async () => {
    simularFetch(
      respuestaJson(200, pagina(1, 1, [fila(1, "ROJO", -1.0)])),
      respuestaJson(400, {
        type: "https://radica.local/problemas/validacion",
        title: "Datos inválidos",
        status: 400,
        detail: "La solicitud tiene 1 error de validación.",
        instance: "/api/v1/pqrs",
        errores: [{ campo: "idArea", mensaje: "Debe ser un número entero." }],
      }),
    );
    const pantalla = await montar(<Bandeja />);

    await escribir(campo(pantalla, "Área sugerida"), "1.5");
    await pulsar(boton(pantalla, "Aplicar"));

    const aviso = pantalla.querySelector('[role="alert"]')!.textContent;
    expect(aviso).toContain("Datos inválidos");
    expect(aviso).toContain("idArea: Debe ser un número entero.");
    expect(pantalla.querySelector("table")).toBeNull();
  });
});

describe("pestañas", () => {
  test("abre el registro por defecto y la bandeja con #bandeja", async () => {
    simularFetch(respuestaJson(200, pagina(1, 0, [])));
    const pantalla = await montar(<App />);
    expect(pantalla.querySelector("h2")!.textContent).toBe("Registrar PQRS");

    await act(async () => {
      window.location.hash = "#bandeja";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      await new Promise((listo) => setTimeout(listo, 0));
    });

    expect(pantalla.querySelector("h2")!.textContent).toBe("Bandeja");
    expect(pantalla.querySelector('a[aria-current="page"]')!.textContent).toBe("Bandeja");
  });
});
