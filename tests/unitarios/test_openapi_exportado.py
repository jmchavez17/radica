"""docs/api/openapi-implementada.json es el OpenAPI que genera la API, sin base de datos.

Si cambia una ruta o un esquema, esta prueba falla hasta regenerar el archivo con
la API en marcha (docker compose up -d), desde la raíz del proyecto:

    curl.exe -s http://127.0.0.1:8000/openapi.json -o openapi.json
    .venv\\Scripts\\python -m json.tool --indent 2 --no-ensure-ascii openapi.json docs\\api\\openapi-implementada.json
"""

import json
from pathlib import Path
from typing import Any

import pytest

from radica.adaptadores.entrada.api.app import crear_app

RUTA = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-implementada.json"

# Las 6 operaciones del contrato docs/api/radica-api-v0.1.yaml que implementa esta entrega.
OPERACIONES_DEL_CONTRATO = {
    "registrarPqrs",
    "listarPqrs",
    "consultarPqrs",
    "solicitarClasificacionIa",
    "consultarHistorial",
    "listarTerminos",
}


def _no_se_usa() -> None:
    raise AssertionError("Generar el OpenAPI no debe abrir casos de uso ni tocar la base.")


@pytest.fixture(scope="module")
def exportado() -> dict[str, Any]:
    return json.loads(RUTA.read_text(encoding="utf-8"))


def test_el_archivo_es_el_openapi_que_genera_la_api(exportado: dict[str, Any]) -> None:
    generado = json.loads(json.dumps(crear_app(_no_se_usa, _no_se_usa).openapi()))  # type: ignore[arg-type]

    assert generado == exportado, "Regenerar docs/api/openapi-implementada.json (ver arriba)."


def test_el_archivo_tiene_las_6_operaciones_del_contrato_y_health(exportado: dict[str, Any]) -> None:
    operaciones = {
        operacion["operationId"]
        for ruta in exportado["paths"].values()
        for operacion in ruta.values()
    }

    assert operaciones - {"salud_health_get"} == OPERACIONES_DEL_CONTRATO
    assert "get" in exportado["paths"]["/health"]
