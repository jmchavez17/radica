// Tipos y catálogos de la API, tomados de docs/api/openapi-implementada.json.
// contrato.test.ts falla si se apartan del OpenAPI que genera la API.

export const CANALES = ["DIME", "CARTA", "CORREO", "WEB", "VERBAL", "BUZON", "APLICATIVO_EPS"] as const;
export const TIPOS_DOCUMENTO = ["CC", "TI", "CE", "PA", "RC", "PPT"] as const;
export const TIPOS_PQRS = [
  "PETICION",
  "QUEJA",
  "RECLAMO",
  "SUGERENCIA",
  "SOLICITUD_INFORMACION",
  "CONSULTA",
] as const;
export const ESTADOS_PQRS = [
  "REGISTRADA",
  "REQUIERE_REVISION",
  "CLASIFICADA",
  "ASIGNADA",
  "EN_RESPUESTA",
  "RESPONDIDA",
  "CERRADA",
] as const;
export const SEMAFOROS = ["VERDE", "AMARILLO", "ROJO"] as const;

export type Canal = (typeof CANALES)[number];
export type TipoDocumento = (typeof TIPOS_DOCUMENTO)[number];
export type TipoPqrs = (typeof TIPOS_PQRS)[number];
export type EstadoPqrs = (typeof ESTADOS_PQRS)[number];
export type Semaforo = (typeof SEMAFOROS)[number];
export type NivelRiesgo = "NO_APLICA" | "SIMPLE" | "PRIORIZADO" | "VITAL";
export type EstadoIa = "PENDIENTE" | "COMPLETADA" | "FALLIDA" | "OMITIDA";
export type OrigenClasificacion = "REGLAS" | "IA" | "PERSONA";

// Límites de PqrsNueva y Peticionario (contexto.md 4.1).
export const LIMITES = {
  sede: 60,
  textoMinimo: 10,
  texto: 10_000,
  numeroDocumento: 20,
  nombre: 150,
  telefono: 20,
} as const;

// Tamaños de página que ofrece la bandeja; la API acepta de 1 a 100 y usa 20 por defecto.
export const TAMANOS_PAGINA = [10, 20, 50, 100] as const;
export const TAMANO_POR_DEFECTO = 20;

export const ETIQUETAS_CANAL: Record<Canal, string> = {
  DIME: "DIME",
  CARTA: "Carta",
  CORREO: "Correo",
  WEB: "Web",
  VERBAL: "Verbal",
  BUZON: "Buzón",
  APLICATIVO_EPS: "Aplicativo de la EPS",
};

export const ETIQUETAS_TIPO: Record<TipoPqrs, string> = {
  PETICION: "Petición",
  QUEJA: "Queja",
  RECLAMO: "Reclamo",
  SUGERENCIA: "Sugerencia",
  SOLICITUD_INFORMACION: "Solicitud de información",
  CONSULTA: "Consulta",
};

export const ETIQUETAS_ESTADO: Record<EstadoPqrs, string> = {
  REGISTRADA: "Registrada",
  REQUIERE_REVISION: "Requiere revisión",
  CLASIFICADA: "Clasificada",
  ASIGNADA: "Asignada",
  EN_RESPUESTA: "En respuesta",
  RESPONDIDA: "Respondida",
  CERRADA: "Cerrada",
};

export const ETIQUETAS_SEMAFORO: Record<Semaforo, string> = {
  VERDE: "Verde",
  AMARILLO: "Amarillo",
  ROJO: "Rojo",
};

export const ETIQUETAS_RIESGO: Record<NivelRiesgo, string> = {
  NO_APLICA: "No aplica",
  SIMPLE: "Simple",
  PRIORIZADO: "Priorizado",
  VITAL: "Vital",
};

export const ETIQUETAS_ESTADO_IA: Record<EstadoIa, string> = {
  PENDIENTE: "Pendiente",
  COMPLETADA: "Completada",
  FALLIDA: "Fallida",
  OMITIDA: "Omitida",
};

export const ETIQUETAS_ORIGEN: Record<OrigenClasificacion, string> = {
  REGLAS: "Reglas",
  IA: "IA",
  PERSONA: "Persona",
};

export interface Referencia {
  id: number;
  nombre: string;
}

export interface Peticionario {
  tipoDocumento?: TipoDocumento;
  numeroDocumento?: string;
  nombre?: string;
  telefono?: string;
  correo?: string;
}

// Los campos van opcionales: si falta uno obligatorio, lo dice el 400 de la API.
export interface PqrsNueva {
  canal?: Canal;
  sede?: string;
  fechaRadicacion?: string;
  texto?: string;
  pacienteMenorDeEdad: boolean;
  peticionario: Peticionario;
}

export interface ClasificacionResumen {
  origen: OrigenClasificacion;
  tipo: TipoPqrs;
  atributo: Referencia | null;
  area: Referencia | null;
  nivelRiesgo: NivelRiesgo;
  confianza: number;
  resumen: string | null;
  requiereRevision: boolean;
  modelo: string | null;
  versionInstrucciones: string | null;
}

export interface Vencimiento {
  fecha: string;
  regla: string;
  semaforo: Semaforo;
  horasRestantes: number;
}

export interface PqrsCreada {
  id: number;
  radicado: string;
  estado: EstadoPqrs;
  estadoIa: EstadoIa;
  clasificacionProvisional: ClasificacionResumen | null;
  vencimiento: Vencimiento;
  posiblesDuplicados?: string[];
}

export interface PqrsResumen {
  id: number;
  radicado: string;
  tipo: TipoPqrs;
  nivelRiesgo: NivelRiesgo;
  area: Referencia | null;
  estado: EstadoPqrs;
  vencimiento: Vencimiento;
}

export interface PaginaPqrs {
  pagina: number;
  total: number;
  elementos: PqrsResumen[];
}

export interface ErrorCampo {
  campo: string;
  mensaje: string;
}

// Problem Details (RFC 9457; contexto.md 4.11).
export interface Problema {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  errores?: ErrorCampo[] | null;
}
