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


class Semaforo(StrEnum):
    """Color de la bandeja según la fracción del plazo que queda (contexto.md 4.7)."""

    VERDE = "VERDE"
    AMARILLO = "AMARILLO"
    ROJO = "ROJO"


class OrigenClasificacion(StrEnum):
    """Quién produjo una clasificación."""

    REGLAS = "REGLAS"
    IA = "IA"
    PERSONA = "PERSONA"


class OrigenEvento(StrEnum):
    """Quién produjo un evento de auditoría."""

    PERSONA = "PERSONA"
    IA = "IA"
    SISTEMA = "SISTEMA"


class AccionAuditoria(StrEnum):
    """Acciones de auditoría de la entrega (contexto.md 4.12). La columna no tiene CHECK."""

    REGISTRAR = "REGISTRAR"
    CLASIFICAR_REGLAS = "CLASIFICAR_REGLAS"
    CALCULAR_VENCIMIENTO = "CALCULAR_VENCIMIENTO"
    CLASIFICAR_IA = "CLASIFICAR_IA"
    SUGERENCIA_IA_NO_APLICADA = "SUGERENCIA_IA_NO_APLICADA"
    IA_FALLIDA = "IA_FALLIDA"
    IA_OMITIDA = "IA_OMITIDA"
    REINTENTO_IA = "REINTENTO_IA"


class ResultadoLlamadaIA(StrEnum):
    """Resultado de un intento de llamada a un proveedor de IA (columna llamada_ia.resultado)."""

    OK = "OK"
    TIMEOUT = "TIMEOUT"
    LIMITE_CUOTA = "LIMITE_CUOTA"
    ERROR_PROVEEDOR = "ERROR_PROVEEDOR"
    CREDENCIAL_INVALIDA = "CREDENCIAL_INVALIDA"
    SALIDA_INVALIDA = "SALIDA_INVALIDA"


class Regimen(StrEnum):
    """Régimen normativo de un término legal."""

    GENERAL = "GENERAL"
    SALUD = "SALUD"


class Poblacion(StrEnum):
    """Población a la que aplica un término. MENOR solo con riesgo VITAL (contexto.md 4.6)."""

    TODAS = "TODAS"
    MENOR = "MENOR"


class Unidad(StrEnum):
    """Unidad en que se cuenta un término legal."""

    DIAS_HABILES = "DIAS_HABILES"
    HORAS_CORRIDAS = "HORAS_CORRIDAS"


class TipoDocumento(StrEnum):
    """Tipo de documento del peticionario, según el contrato de la API."""

    CC = "CC"
    TI = "TI"
    CE = "CE"
    PA = "PA"
    RC = "RC"
    PPT = "PPT"
