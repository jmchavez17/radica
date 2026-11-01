import { describe, expect, test, vi } from "vitest";
import { SIN_CONEXION, listarPqrs, registrarPqrs, urlBandeja } from "../api";
import type { PqrsNueva } from "../tipos";
import { respuestaJson, respuestaSinJson, simularFetch } from "./ayudantes";

const NUEVA: PqrsNueva = {
  canal: "DIME",
  fechaRadicacion: "2026-10-30T16:00:00-05:00",
  texto: "Texto sintético de prueba.",
  pacienteMenorDeEdad: false,
  peticionario: { tipoDocumento: "CC", numeroDocumento: "1000000001", nombre: "Usuario Sintético" },
};

const SIN_FILTROS = { semaforo: "", estado: "", tipo: "", idArea: "" } as const;

describe("registrarPqrs", () => {
  test("envía la PQRS como JSON a POST /api/v1/pqrs y devuelve el cuerpo del 201", async () => {
    const creada = { id: 7, radicado: "RAD-2026-000007" };
    const fetch = simularFetch(respuestaJson(201, creada));

    const resultado = await registrarPqrs(NUEVA);

    expect(resultado).toEqual({ ok: true, datos: creada });
    const [url, opciones] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/pqrs");
    expect(opciones?.method).toBe("POST");
    expect(opciones?.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(String(opciones?.body))).toEqual(NUEVA);
  });

  test("un 400 devuelve los errores por campo de Problem Details", async () => {
    const errores = [
      { campo: "texto", mensaje: "Debe tener al menos 10 caracteres." },
      { campo: "peticionario.nombre", mensaje: "El nombre es obligatorio." },
    ];
    simularFetch(
      respuestaJson(400, {
        type: "https://radica.local/problemas/validacion",
        title: "Datos inválidos",
        status: 400,
        detail: "La solicitud tiene 2 errores de validación.",
        instance: "/api/v1/pqrs",
        errores,
      }),
    );

    const resultado = await registrarPqrs(NUEVA);

    expect(resultado).toEqual({
      ok: false,
      fallo: { titulo: "Datos inválidos", detalle: "La solicitud tiene 2 errores de validación.", errores },
    });
  });

  test("un 500 devuelve el título y el detalle, sin errores por campo", async () => {
    simularFetch(
      respuestaJson(500, {
        type: "https://radica.local/problemas/configuracion",
        title: "Configuración incompleta",
        status: 500,
        detail: "No se pudo calcular el vencimiento.",
        instance: "/api/v1/pqrs",
      }),
    );

    const resultado = await registrarPqrs(NUEVA);

    expect(resultado).toEqual({
      ok: false,
      fallo: { titulo: "Configuración incompleta", detalle: "No se pudo calcular el vencimiento.", errores: [] },
    });
  });

  test("una respuesta sin Problem Details, como el 502 de nginx, da el código", async () => {
    simularFetch(respuestaSinJson(502));

    const resultado = await registrarPqrs(NUEVA);

    expect(resultado).toEqual({
      ok: false,
      fallo: { titulo: "Error 502", detalle: "La API no respondió con Problem Details.", errores: [] },
    });
  });

  test("sin conexión con la API", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch")));

    expect(await registrarPqrs(NUEVA)).toEqual({ ok: false, fallo: SIN_CONEXION });
  });
});

describe("bandeja", () => {
  test("sin filtros pide solo la página y el tamaño", () => {
    expect(urlBandeja(SIN_FILTROS, 1, 20)).toBe("/api/v1/pqrs?pagina=1&tamano=20");
  });

  test("envía los filtros puestos con los nombres de la API", () => {
    const filtros = { semaforo: "ROJO", estado: "REQUIERE_REVISION", tipo: "RECLAMO", idArea: " 4 " } as const;

    expect(urlBandeja(filtros, 3, 50)).toBe(
      "/api/v1/pqrs?semaforo=ROJO&estado=REQUIERE_REVISION&tipo=RECLAMO&idArea=4&pagina=3&tamano=50",
    );
  });

  test("devuelve la página tal como la entrega la API", async () => {
    const pagina = { pagina: 1, total: 0, elementos: [] };
    const fetch = simularFetch(respuestaJson(200, pagina));

    expect(await listarPqrs({ ...SIN_FILTROS, semaforo: "VERDE" }, 1, 10)).toEqual({ ok: true, datos: pagina });
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/pqrs?semaforo=VERDE&pagina=1&tamano=10");
  });
});
