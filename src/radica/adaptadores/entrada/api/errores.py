"""Errores en formato Problem Details (RFC 9457; contexto.md 4.11).

La validación responde 400, no el 422 de FastAPI. Los mensajes están en
español y nunca repiten el valor recibido. Un 500 no lleva detalles internos.
"""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from radica.aplicacion.casos_de_uso.errores import DatosInvalidos, OperacionNoPermitida, PqrsNoEncontrada
from radica.dominio.plazos import TerminoNoConfigurado

registro = logging.getLogger("radica.api")

TIPO_BASE = "https://radica.local/problemas/"
TIPO_CONTENIDO = "application/problem+json"

OBLIGATORIOS = {
    "canal": "El canal es obligatorio.",
    "fechaRadicacion": "La fecha de radicación es obligatoria.",
    "texto": "El texto es obligatorio.",
    "peticionario": "Los datos del peticionario son obligatorios.",
    "peticionario.tipoDocumento": "El tipo de documento es obligatorio.",
    "peticionario.numeroDocumento": "El número de documento es obligatorio.",
    "peticionario.nombre": "El nombre es obligatorio.",
    "cuerpo": "El cuerpo de la solicitud es obligatorio.",
}
MENSAJE_FECHA = "Debe ser una fecha ISO 8601 con zona horaria."

TITULOS = {404: "Recurso no encontrado", 405: "Método no permitido"}


def problema(
    request: Request,
    estado: int,
    tipo: str,
    titulo: str,
    detalle: str,
    errores: Sequence[dict[str, str]] | None = None,
) -> JSONResponse:
    cuerpo: dict[str, Any] = {
        "type": TIPO_BASE + tipo,
        "title": titulo,
        "status": estado,
        "detail": detalle,
        "instance": request.url.path,
    }
    if errores is not None:
        cuerpo["errores"] = list(errores)
    return JSONResponse(cuerpo, status_code=estado, media_type=TIPO_CONTENIDO)


def _campo(ubicacion: Sequence[str | int]) -> str:
    partes = [str(parte) for parte in ubicacion[1:] if isinstance(parte, str)]
    return ".".join(partes) if partes else "cuerpo"


def _mensaje(campo: str, error: dict[str, Any]) -> str:
    tipo = error["type"]
    contexto = error.get("ctx") or {}
    entrada = error.get("input")
    vacio = isinstance(entrada, str) and not entrada.strip()
    if tipo == "missing" or (tipo == "string_too_short" and vacio):
        return OBLIGATORIOS.get(campo, "Es obligatorio.")
    if tipo == "json_invalid":
        return "El cuerpo no es un JSON válido."
    if tipo.startswith(("datetime", "timezone")):
        return MENSAJE_FECHA
    if tipo == "string_too_short":
        return f"Debe tener al menos {contexto.get('min_length')} caracteres."
    if tipo == "string_too_long":
        return f"Debe tener máximo {contexto.get('max_length')} caracteres."
    if tipo == "string_pattern_mismatch":
        return "Debe ser un correo electrónico válido."
    if tipo == "enum":
        opciones = str(contexto.get("expected", "")).replace("'", "").replace(" or ", ", ")
        return f"Debe ser uno de: {opciones}."
    if tipo in {"int_parsing", "int_type", "int_from_float"}:
        return "Debe ser un número entero."
    if tipo == "greater_than_equal":
        return f"Debe ser mayor o igual a {contexto.get('ge')}."
    if tipo == "less_than_equal":
        return f"Debe ser menor o igual a {contexto.get('le')}."
    if tipo in {"bool_parsing", "bool_type"}:
        return "Debe ser verdadero o falso."
    if tipo == "string_type":
        return "Debe ser un texto."
    if tipo in {"model_type", "model_attributes_type", "dict_type"}:
        return "Debe ser un objeto JSON."
    return "Valor inválido."


def _validacion(request: Request, errores: list[dict[str, str]]) -> JSONResponse:
    cantidad = len(errores)
    detalle = f"La solicitud tiene {cantidad} {'error' if cantidad == 1 else 'errores'} de validación."
    return problema(request, 400, "validacion", "Datos inválidos", detalle, errores)


async def _de_esquema(request: Request, error: RequestValidationError) -> JSONResponse:
    errores = []
    for detalle in error.errors():
        campo = _campo(detalle.get("loc", ()))
        errores.append({"campo": campo, "mensaje": _mensaje(campo, detalle)})
    return _validacion(request, errores)


async def _de_negocio(request: Request, error: DatosInvalidos) -> JSONResponse:
    return _validacion(
        request, [{"campo": to_camel(e.campo), "mensaje": e.mensaje} for e in error.errores]
    )


async def _no_encontrada(request: Request, error: PqrsNoEncontrada) -> JSONResponse:
    return problema(
        request, 404, "no-encontrado", "Recurso no encontrado", f"No existe la PQRS {error.id_pqrs}."
    )


async def _conflicto(request: Request, error: OperacionNoPermitida) -> JSONResponse:
    return problema(request, 409, "conflicto", "Operación no permitida", error.detalle)


async def _http(request: Request, error: StarletteHTTPException) -> JSONResponse:
    titulo = TITULOS.get(error.status_code, "Error en la solicitud")
    detalle = "La ruta no existe." if error.status_code == 404 else titulo + "."
    return problema(request, error.status_code, "http", titulo, detalle)


async def _termino_no_configurado(request: Request, error: TerminoNoConfigurado) -> JSONResponse:
    registro.error("Término legal no configurado en %s: %s", request.url.path, error)
    return problema(
        request,
        500,
        "configuracion",
        "Configuración incompleta",
        "No hay un término legal vigente para esta clasificación. Avise al administrador.",
    )


async def _interno(request: Request, error: Exception) -> JSONResponse:
    registro.exception("Error no controlado en %s %s", request.method, request.url.path)
    return problema(request, 500, "interno", "Error interno", "No se pudo completar la solicitud.")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _de_esquema)
    app.add_exception_handler(DatosInvalidos, _de_negocio)
    app.add_exception_handler(PqrsNoEncontrada, _no_encontrada)
    app.add_exception_handler(OperacionNoPermitida, _conflicto)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(TerminoNoConfigurado, _termino_no_configurado)
    app.add_exception_handler(Exception, _interno)
