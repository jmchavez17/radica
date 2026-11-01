// Los catálogos y límites de tipos.ts deben coincidir con el OpenAPI que genera la API.
// En Docker el archivo llega por el contexto «contrato» a /docs/api (web/Dockerfile).
import { describe, expect, test } from "vitest";
import openapi from "../../../docs/api/openapi-implementada.json";
import {
  CANALES,
  ESTADOS_PQRS,
  ETIQUETAS_ESTADO_IA,
  ETIQUETAS_ORIGEN,
  ETIQUETAS_RIESGO,
  LIMITES,
  SEMAFOROS,
  TAMANOS_PAGINA,
  TAMANO_POR_DEFECTO,
  TIPOS_DOCUMENTO,
  TIPOS_PQRS,
} from "../tipos";

interface Esquema {
  enum?: string[];
  properties?: Record<string, Esquema>;
  anyOf?: Esquema[];
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  default?: number;
}

interface Parametro {
  name: string;
  schema: Esquema;
}

const esquemas = openapi.components.schemas as unknown as Record<string, Esquema>;
const parametrosBandeja = openapi.paths["/api/v1/pqrs"].get.parameters as unknown as Parametro[];

function propiedad(esquema: string, nombre: string): Esquema {
  const encontrada = esquemas[esquema].properties![nombre];
  // Los opcionales salen como anyOf [texto, null].
  return encontrada.anyOf?.[0] ?? encontrada;
}

describe("catálogos", () => {
  test.each([
    ["Canal", CANALES],
    ["TipoDocumento", TIPOS_DOCUMENTO],
    ["TipoPqrs", TIPOS_PQRS],
    ["EstadoPqrs", ESTADOS_PQRS],
    ["Semaforo", SEMAFOROS],
    ["NivelRiesgo", Object.keys(ETIQUETAS_RIESGO)],
    ["EstadoIa", Object.keys(ETIQUETAS_ESTADO_IA)],
    ["OrigenClasificacion", Object.keys(ETIQUETAS_ORIGEN)],
  ])("%s", (nombre, valores) => {
    expect([...valores]).toEqual(esquemas[nombre].enum);
  });
});

describe("límites del registro (contexto.md 4.1)", () => {
  test("sede y texto", () => {
    expect(propiedad("PqrsNueva", "sede").maxLength).toBe(LIMITES.sede);
    expect(propiedad("PqrsNueva", "texto").minLength).toBe(LIMITES.textoMinimo);
    expect(propiedad("PqrsNueva", "texto").maxLength).toBe(LIMITES.texto);
  });

  test("peticionario", () => {
    expect(propiedad("Peticionario", "numeroDocumento").maxLength).toBe(LIMITES.numeroDocumento);
    expect(propiedad("Peticionario", "nombre").maxLength).toBe(LIMITES.nombre);
    expect(propiedad("Peticionario", "telefono").maxLength).toBe(LIMITES.telefono);
  });
});

describe("parámetros de la bandeja", () => {
  test("la API acepta los filtros que envía la interfaz", () => {
    expect(parametrosBandeja.map((p) => p.name).sort()).toEqual(
      ["estado", "idArea", "pagina", "semaforo", "tamano", "tipo"].sort(),
    );
  });

  test("los tamaños de página caben en el máximo y el defecto es el de la API", () => {
    const tamano = parametrosBandeja.find((p) => p.name === "tamano")!.schema;
    expect(Math.max(...TAMANOS_PAGINA)).toBeLessThanOrEqual(tamano.maximum!);
    expect(Math.min(...TAMANOS_PAGINA)).toBeGreaterThanOrEqual(tamano.minimum!);
    expect(tamano.default).toBe(TAMANO_POR_DEFECTO);
    expect(TAMANOS_PAGINA).toContain(TAMANO_POR_DEFECTO);
  });
});
