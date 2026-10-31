"""Tipos de valor del dominio de Radica.

Son los valores cerrados del modelo de datos v1.1 (docs/modelo-datos.md) y del
contrato de la API (docs/api/radica-api-v0.1.yaml), en español y en
mayúsculas, igual que en la base de datos y en la API.
"""

from enum import StrEnum


class TipoPqrs(StrEnum):
    """Tipo de PQRS. SOLICITUD_INFORMACION tiene 21 caracteres: por eso las columnas son VARCHAR(25)."""

    PETICION = "PETICION"
    QUEJA = "QUEJA"
    RECLAMO = "RECLAMO"
    SUGERENCIA = "SUGERENCIA"
    SOLICITUD_INFORMACION = "SOLICITUD_INFORMACION"
    CONSULTA = "CONSULTA"


class NivelRiesgo(StrEnum):
    """Nivel de riesgo, declarado de menor a mayor gravedad.

    La comparación de gravedad la hará la regla PoliticaDeRiesgo, no este tipo.
    """

    NO_APLICA = "NO_APLICA"
    SIMPLE = "SIMPLE"
    PRIORIZADO = "PRIORIZADO"
    VITAL = "VITAL"


class Canal(StrEnum):
    """Medio por el que llegó la PQRS."""

    DIME = "DIME"
    CARTA = "CARTA"
    CORREO = "CORREO"
    WEB = "WEB"
    VERBAL = "VERBAL"
    BUZON = "BUZON"
    APLICATIVO_EPS = "APLICATIVO_EPS"


class EstadoPqrs(StrEnum):
    """Estado de gestión de la PQRS."""

    REGISTRADA = "REGISTRADA"
    REQUIERE_REVISION = "REQUIERE_REVISION"
    CLASIFICADA = "CLASIFICADA"
    ASIGNADA = "ASIGNADA"
    EN_RESPUESTA = "EN_RESPUESTA"
    RESPONDIDA = "RESPONDIDA"
    CERRADA = "CERRADA"


class EstadoIa(StrEnum):
    """Estado de la clasificación con IA, que se procesa en segundo plano (ADR-04)."""

    PENDIENTE = "PENDIENTE"
    COMPLETADA = "COMPLETADA"
    FALLIDA = "FALLIDA"
    OMITIDA = "OMITIDA"
