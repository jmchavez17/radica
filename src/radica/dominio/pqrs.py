"""Entidades de la PQRS, su clasificación y sus eventos de auditoría."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from radica.dominio.plazos import dia_en_colombia
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    TipoPqrs,
)


def formato_radicado(id_pqrs: int, fecha_radicacion: datetime) -> str:
    """RAD-<año de radicación en Colombia>-<id con 6 dígitos> (contexto.md 4.3)."""
    return f"RAD-{dia_en_colombia(fecha_radicacion).year}-{id_pqrs:06d}"


@dataclass(frozen=True)
class Referencia:
    id: int
    nombre: str


@dataclass(frozen=True)
class PeticionarioCifrado:
    """Fila de peticionario: solo el HMAC del documento y los datos cifrados."""

    documento_hash: str
    nombre_cifrado: bytes = field(repr=False)
    contacto_cifrado: bytes = field(repr=False)


@dataclass(frozen=True)
class Pqrs:
    """Fila de pqrs al registrarla."""

    id: int
    radicado: str
    id_peticionario: int
    canal: Canal
    sede: str | None
    fecha_radicacion: datetime
    texto_original_cifrado: bytes = field(repr=False)
    texto_enmascarado: str
    tipo: TipoPqrs
    id_atributo: int | None
    nivel_riesgo: NivelRiesgo
    paciente_menor: bool
    id_termino: int
    fecha_vencimiento: datetime
    estado: EstadoPqrs
    estado_ia: EstadoIa


@dataclass(frozen=True)
class Clasificacion:
    """Fila de clasificacion."""

    origen: OrigenClasificacion
    tipo: TipoPqrs
    id_atributo: int | None
    id_area: int | None
    nivel_riesgo: NivelRiesgo
    confianza: float
    resumen: str | None = None
    datos_extraidos: Mapping[str, str] | None = None
    id_llamada_ia: int | None = None
    vigente: bool = True


@dataclass(frozen=True)
class EventoAuditoria:
    """Fila de auditoria. La fecha y el id los pone la base al insertar."""

    id_pqrs: int
    origen: OrigenEvento
    accion: AccionAuditoria
    id_usuario: int | None = None
    campo: str | None = None
    valor_anterior: str | None = None
    valor_nuevo: str | None = None
    motivo: str | None = None
    id_evento: int | None = None
    fecha: datetime | None = None
