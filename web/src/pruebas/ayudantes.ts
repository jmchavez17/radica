// Ayudantes de las pruebas: respuestas falsas de la API, sin red.
import { vi } from "vitest";

export function respuestaJson(estado: number, cuerpo: unknown): Response {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    json: () => Promise.resolve(cuerpo),
  } as Response;
}

export function respuestaSinJson(estado: number): Response {
  return {
    ok: false,
    status: estado,
    json: () => Promise.reject(new SyntaxError("No es JSON")),
  } as Response;
}

// Sustituye fetch por un doble que responde en orden lo que se le pase.
export function simularFetch(...respuestas: Response[]) {
  const doble = vi.fn<typeof fetch>();
  for (const respuesta of respuestas) doble.mockResolvedValueOnce(respuesta);
  vi.stubGlobal("fetch", doble);
  return doble;
}
