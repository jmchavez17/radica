import { describe, expect, test, vi } from "vitest";
import { Registro } from "../Registro";
import type { PqrsCreada } from "../tipos";
import { boton, campo, escribir, mensajeDe, montar, pulsar, respuestaJson, simularFetch } from "./ayudantes";

const CREADA: PqrsCreada = {
  id: 9,
  radicado: "RAD-2026-000009",
  estado: "REGISTRADA",
  estadoIa: "PENDIENTE",
  clasificacionProvisional: {
    origen: "REGLAS",
    tipo: "RECLAMO",
    atributo: null,
    area: { id: 4, nombre: "Autorizaciones" },
    nivelRiesgo: "SIMPLE",
    confianza: 0.5,
    resumen: null,
    requiereRevision: false,
    modelo: null,
    versionInstrucciones: null,
  },
  // ROJO con 70 horas a propósito: la interfaz muestra el semáforo de la API, no lo recalcula.
  vencimiento: {
    fecha: "2026-11-02T16:00:00-05:00",
    regla: "Reclamo en salud, riesgo simple: 72 horas corridas",
    semaforo: "ROJO",
    horasRestantes: 70.0,
  },
  posiblesDuplicados: [],
};

const TEXTO = "Desde hace tres semanas espero la autorización de una resonancia.";

async function llenar(contenedor: HTMLElement) {
  await escribir(campo(contenedor, "Canal"), "DIME");
  await escribir(campo(contenedor, "Fecha y hora de radicación"), "2026-10-30T16:00");
  await escribir(campo(contenedor, "Texto"), TEXTO);
  await escribir(campo(contenedor, "Tipo de documento"), "CC");
  await escribir(campo(contenedor, "Número de documento"), "1000000001");
  await escribir(campo(contenedor, "Nombre"), "Usuario Sintético Uno");
  await escribir(campo(contenedor, "Correo"), "usuario01@radica.test");
}

function cuerpoEnviado(fetch: ReturnType<typeof simularFetch>) {
  return JSON.parse(String(fetch.mock.calls[0][1]?.body));
}

describe("registro de una PQRS", () => {
  test("envía los campos de 4.1 con la hora de Colombia y sin los opcionales vacíos", async () => {
    const fetch = simularFetch(respuestaJson(201, CREADA));
    const pantalla = await montar(<Registro />);
    await llenar(pantalla);
    await pulsar(campo(pantalla, "Paciente menor de edad"));

    await pulsar(boton(pantalla, "Registrar PQRS"));

    expect(fetch.mock.calls[0][0]).toBe("/api/v1/pqrs");
    expect(cuerpoEnviado(fetch)).toEqual({
      canal: "DIME",
      fechaRadicacion: "2026-10-30T16:00:00-05:00",
      texto: TEXTO,
      pacienteMenorDeEdad: true,
      peticionario: {
        tipoDocumento: "CC",
        numeroDocumento: "1000000001",
        nombre: "Usuario Sintético Uno",
        correo: "usuario01@radica.test",
      },
    });
  });

  test("muestra el radicado, la clasificación provisional y el vencimiento que devuelve la API", async () => {
    simularFetch(respuestaJson(201, CREADA));
    const pantalla = await montar(<Registro />);
    await llenar(pantalla);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    const resultado = pantalla.querySelector('[aria-label="PQRS registrada"]')!;
    const texto = resultado.textContent ?? "";
    expect(texto).toContain("RAD-2026-000009");
    expect(texto).toContain("Clasificación con IA: Pendiente");
    for (const dato of ["Reglas", "Reclamo", "Simple", "Sin atributo", "Autorizaciones", "0,50"]) {
      expect(texto).toContain(dato);
    }
    expect(texto).toContain("Reclamo en salud, riesgo simple: 72 horas corridas");
    expect(texto).toContain("70,0 h");
    const semaforo = resultado.querySelector(".semaforo")!;
    expect(semaforo.className).toContain("semaforo-rojo");
    expect(semaforo.textContent).toBe("Rojo");
  });

  test("vacía el formulario después del registro y no guarda nada en el navegador", async () => {
    simularFetch(respuestaJson(201, CREADA));
    const pantalla = await montar(<Registro />);
    await llenar(pantalla);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    for (const etiqueta of ["Número de documento", "Nombre", "Correo", "Texto"]) {
      expect(campo(pantalla, etiqueta).value).toBe("");
    }
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  test("muestra cada error 400 debajo de su campo y los demás en el resumen", async () => {
    const fetch = simularFetch(
      respuestaJson(400, {
        type: "https://radica.local/problemas/validacion",
        title: "Datos inválidos",
        status: 400,
        detail: "La solicitud tiene 4 errores de validación.",
        instance: "/api/v1/pqrs",
        errores: [
          { campo: "canal", mensaje: "El canal es obligatorio." },
          { campo: "texto", mensaje: "El texto es obligatorio." },
          { campo: "peticionario.nombre", mensaje: "El nombre es obligatorio." },
          { campo: "cuerpo", mensaje: "El cuerpo de la solicitud es obligatorio." },
        ],
      }),
    );
    const pantalla = await montar(<Registro />);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    // Con el formulario vacío la interfaz no valida nada: envía y la API responde.
    expect(cuerpoEnviado(fetch)).toEqual({ pacienteMenorDeEdad: false, peticionario: {} });
    for (const [etiqueta, mensaje] of [
      ["Canal", "El canal es obligatorio."],
      ["Texto", "El texto es obligatorio."],
      ["Nombre", "El nombre es obligatorio."],
    ]) {
      expect(campo(pantalla, etiqueta).getAttribute("aria-invalid")).toBe("true");
      expect(mensajeDe(campo(pantalla, etiqueta))).toBe(mensaje);
    }
    expect(campo(pantalla, "Sede").hasAttribute("aria-invalid")).toBe(false);
    const resumen = pantalla.querySelector('[role="alert"]')!.textContent;
    expect(resumen).toContain("Datos inválidos");
    expect(resumen).toContain("La solicitud tiene 4 errores de validación.");
    expect(resumen).toContain("cuerpo: El cuerpo de la solicitud es obligatorio.");
    expect(resumen).not.toContain("El canal es obligatorio.");
  });

  test("conserva lo escrito cuando la API responde 400", async () => {
    simularFetch(
      respuestaJson(400, {
        type: "https://radica.local/problemas/validacion",
        title: "Datos inválidos",
        status: 400,
        detail: "La solicitud tiene 1 error de validación.",
        instance: "/api/v1/pqrs",
        errores: [{ campo: "peticionario.correo", mensaje: "Debe ser un correo electrónico válido." }],
      }),
    );
    const pantalla = await montar(<Registro />);
    await llenar(pantalla);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    expect(campo(pantalla, "Nombre").value).toBe("Usuario Sintético Uno");
    expect(mensajeDe(campo(pantalla, "Correo"))).toBe("Debe ser un correo electrónico válido.");
  });

  test("un 500 muestra el título y el detalle de Problem Details", async () => {
    simularFetch(
      respuestaJson(500, {
        type: "https://radica.local/problemas/configuracion",
        title: "Configuración incompleta",
        status: 500,
        detail: "No hay un término legal vigente para esta clasificación.",
        instance: "/api/v1/pqrs",
      }),
    );
    const pantalla = await montar(<Registro />);
    await llenar(pantalla);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    const resumen = pantalla.querySelector('[role="alert"]')!.textContent;
    expect(resumen).toContain("Configuración incompleta");
    expect(resumen).toContain("No hay un término legal vigente para esta clasificación.");
    expect(pantalla.querySelector('[aria-label="PQRS registrada"]')).toBeNull();
  });

  test("sin conexión con la API", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch")));
    const pantalla = await montar(<Registro />);

    await pulsar(boton(pantalla, "Registrar PQRS"));

    expect(pantalla.querySelector('[role="alert"]')!.textContent).toContain("No se pudo conectar con la API.");
  });
});
