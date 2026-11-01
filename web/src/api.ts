// Cliente de la API. Las rutas son relativas: nginx las lleva al servicio api, en el
// mismo origen. La interfaz no valida ni calcula nada: muestra lo que responde la API.
import type { EstadoPqrs, ErrorCampo, PaginaPqrs, PqrsCreada, PqrsNueva, Problema, Semaforo, TipoPqrs } from "./tipos";

export interface Fallo {
  titulo: string;
  detalle: string;
  errores: ErrorCampo[];
}

export type Resultado<T> = { ok: true; datos: T } | { ok: false; fallo: Fallo };

export const SIN_CONEXION: Fallo = {
  titulo: "Sin conexión",
  detalle: "No se pudo conectar con la API.",
  errores: [],
};

async function leerFallo(respuesta: Response): Promise<Fallo> {
  try {
    const problema = (await respuesta.json()) as Partial<Problema>;
    return {
      titulo: problema.title ?? `Error ${respuesta.status}`,
      detalle: problema.detail ?? "",
      errores: Array.isArray(problema.errores) ? problema.errores : [],
    };
  } catch {
    return {
      titulo: `Error ${respuesta.status}`,
      detalle: "La API no respondió con Problem Details.",
      errores: [],
    };
  }
}

async function pedir<T>(url: string, opciones: RequestInit = {}): Promise<Resultado<T>> {
  let respuesta: Response;
  try {
    respuesta = await fetch(url, {
      ...opciones,
      cache: "no-store",
      headers: { Accept: "application/json", ...opciones.headers },
    });
  } catch {
    return { ok: false, fallo: SIN_CONEXION };
  }
  if (!respuesta.ok) return { ok: false, fallo: await leerFallo(respuesta) };
  return { ok: true, datos: (await respuesta.json()) as T };
}

export function registrarPqrs(pqrs: PqrsNueva): Promise<Resultado<PqrsCreada>> {
  return pedir<PqrsCreada>("/api/v1/pqrs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pqrs),
  });
}

// Un filtro vacío no se envía. idArea va como texto: si no es un entero, lo dice la API.
export interface FiltrosBandeja {
  semaforo: Semaforo | "";
  estado: EstadoPqrs | "";
  tipo: TipoPqrs | "";
  idArea: string;
}

export function urlBandeja(filtros: FiltrosBandeja, pagina: number, tamano: number): string {
  const consulta = new URLSearchParams();
  for (const [nombre, valor] of Object.entries(filtros)) {
    if (valor.trim() !== "") consulta.set(nombre, valor.trim());
  }
  consulta.set("pagina", String(pagina));
  consulta.set("tamano", String(tamano));
  return `/api/v1/pqrs?${consulta}`;
}

export function listarPqrs(filtros: FiltrosBandeja, pagina: number, tamano: number): Promise<Resultado<PaginaPqrs>> {
  return pedir<PaginaPqrs>(urlBandeja(filtros, pagina, tamano));
}
