"""Aplicación FastAPI: rutas, manejo de errores, /health y el OpenAPI con 400 en vez de 422."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from radica.adaptadores.entrada.api.casos import FabricaDeCasos
from radica.adaptadores.entrada.api.errores import TIPO_CONTENIDO, problema, registrar_manejadores, registro
from radica.adaptadores.entrada.api.rutas import crear_rutas

DESCRIPCION = """
API del asistente de gestión de PQRS Radica (Entrega 3). Implementa 5 de las
13 operaciones del contrato `docs/api/radica-api-v0.1.yaml` más `GET /health`.

- JSON en camelCase; fechas ISO 8601 con zona horaria (America/Bogota, -05:00).
- Errores en Problem Details (RFC 9457), `application/problem+json`. La
  validación responde 400.
- Sin autenticación en esta entrega: las acciones se atribuyen al usuario
  semilla «Funcionario Sintético» (contexto.md 4.12).
- Todos los datos son sintéticos. Ninguna respuesta lleva datos del peticionario.
"""

EJEMPLO_400 = {
    "type": "https://radica.local/problemas/validacion",
    "title": "Datos inválidos",
    "status": 400,
    "detail": "La solicitud tiene 2 errores de validación.",
    "instance": "/api/v1/pqrs",
    "errores": [
        {"campo": "texto", "mensaje": "El texto es obligatorio."},
        {"campo": "fechaRadicacion", "mensaje": "Debe ser una fecha ISO 8601 con zona horaria."},
    ],
}


def _openapi(app: FastAPI) -> Callable[[], dict[str, Any]]:
    """Quita el 422 que FastAPI agrega a cada ruta y publica los errores como problem+json."""

    def generar() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        esquema = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes
        )
        for ruta in esquema["paths"].values():
            for operacion in ruta.values():
                respuestas = operacion.get("responses", {})
                respuestas.pop("422", None)
                for codigo, respuesta in respuestas.items():
                    contenido = respuesta.get("content", {})
                    if int(codigo) >= 400 and "application/json" in contenido:
                        respuesta["content"] = {TIPO_CONTENIDO: contenido["application/json"]}
                if "400" in respuestas and operacion.get("operationId") == "registrarPqrs":
                    respuestas["400"]["content"][TIPO_CONTENIDO]["example"] = EJEMPLO_400
        componentes = esquema.get("components", {}).get("schemas", {})
        componentes.pop("HTTPValidationError", None)
        componentes.pop("ValidationError", None)
        app.openapi_schema = esquema
        return esquema

    return generar


def crear_app(fabrica: FabricaDeCasos, comprobar_base: Callable[[], None]) -> FastAPI:
    """comprobar_base lanza una excepción si la base de datos no responde."""
    app = FastAPI(title="Radica API", version="0.1.0", description=DESCRIPCION)
    registrar_manejadores(app)
    app.include_router(crear_rutas(fabrica))

    @app.get("/health", tags=["Técnico"], summary="Estado de la API y de la base de datos")
    def salud(request: Request) -> JSONResponse:
        try:
            comprobar_base()
        except Exception:
            registro.exception("La base de datos no responde")
            return problema(
                request, 503, "no-disponible", "Servicio no disponible", "La base de datos no responde."
            )
        return JSONResponse({"estado": "ok"})

    app.openapi = _openapi(app)  # type: ignore[method-assign]
    return app
