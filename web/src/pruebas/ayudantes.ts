// Ayudantes de las pruebas: respuestas falsas de la API, sin red, y manejo del DOM con
// el act() de React, sin otras bibliotecas.
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, vi } from "vitest";

const desmontar: Array<() => void> = [];

afterEach(() => {
  for (const fin of desmontar.splice(0)) act(fin);
});

// Deja que terminen las promesas pendientes, como la respuesta de fetch.
function esperar(): Promise<void> {
  return new Promise((listo) => setTimeout(listo, 0));
}

export async function montar(elemento: ReactNode): Promise<HTMLElement> {
  const contenedor = document.createElement("div");
  document.body.append(contenedor);
  const raiz = createRoot(contenedor);
  desmontar.push(() => raiz.unmount());
  await act(async () => {
    raiz.render(elemento);
    await esperar();
  });
  return contenedor;
}

type Control = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

// El control cuya etiqueta empieza con el texto dado.
export function campo(contenedor: HTMLElement, etiqueta: string): Control {
  const encontrada = [...contenedor.querySelectorAll("label")].find((l) =>
    (l.textContent ?? "").trim().startsWith(etiqueta),
  );
  if (!encontrada?.control) throw new Error(`No hay un campo «${etiqueta}»`);
  return encontrada.control as Control;
}

// Cambia el valor como lo haría una persona, para que React reciba el evento.
export async function escribir(control: Control, valor: string): Promise<void> {
  const asignar = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(control), "value")!.set!;
  await act(async () => {
    asignar.call(control, valor);
    control.dispatchEvent(new Event(control instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
  });
}

export async function pulsar(elemento: Element): Promise<void> {
  await act(async () => {
    (elemento as HTMLElement).click();
    await esperar();
  });
}

export function boton(contenedor: HTMLElement, texto: string): HTMLButtonElement {
  const encontrado = [...contenedor.querySelectorAll("button")].find((b) => b.textContent?.trim() === texto);
  if (!encontrado) throw new Error(`No hay un botón «${texto}»`);
  return encontrado;
}

export function mensajeDe(control: Control): string | null {
  const id = control.getAttribute("aria-describedby");
  return id ? (document.getElementById(id)?.textContent ?? null) : null;
}

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
