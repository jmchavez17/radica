"""Errores de la API en Problem Details, sin base de datos (contexto.md 4.11).

La API se arma con los casos de uso sobre dobles en memoria.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from dobles import AuditoriaEnMemoria, ClasificadorFijo, ConfiguracionEnMemoria, PqrsEnMemoria
from fastapi.testclient import TestClient

from radica.adaptadores.entrada.api.app import crear_app
from radica.adaptadores.entrada.api.casos import CasosDeUso
from radica.adaptadores.entrada.api.esquemas import EJEMPLO_REGISTRO
from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.aplicacion.casos_de_uso.consultas import (
    ConsultarHistorial,
    ConsultarPqrs,
    ListarBandeja,
    ListarTerminos,
)
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs
from radica.aplicacion.casos_de_uso.solicitar_clasificacion import SolicitarClasificacion
from radica.aplicacion.puertos.clasificador import ResultadoClasificacion
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos, Termino
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import NivelRiesgo, TipoPqrs

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
PROBLEMA = "application/problem+json"


class _Falla(Exception):
    """Simula un error interno con un mensaje que no debe salir en la respuesta."""


def _cliente(
    terminos: tuple[Termino, ...],
    festivos: frozenset[date],
    falla: Exception | None = None,
    base_responde: bool = True,
) -> TestClient:
    pqrs, auditoria = PqrsEnMemoria(), AuditoriaEnMemoria()
    configuracion = ConfiguracionEnMemoria(terminos, festivos)
    semaforo = ReglaSemaforo(0.5)
    resultado = ResultadoClasificacion(TipoPqrs.RECLAMO, None, 4, NivelRiesgo.SIMPLE, 0.5)

    @contextmanager
    def fabrica() -> Iterator[CasosDeUso]:
        if falla is not None:
            raise falla
        yield CasosDeUso(
            registrar=RegistrarPqrs(
                pqrs, auditoria, configuracion, CifradorAesGcm(os.urandom(32), os.urandom(32)),
                EnmascaradorReglas(), ClasificadorFijo(resultado), CalculadoraDePlazos(), semaforo,
                lambda: AHORA, 1, "clasif-v1.0",
            ),
            consultar=ConsultarPqrs(pqrs, semaforo, lambda: AHORA),
            bandeja=ListarBandeja(pqrs, semaforo, lambda: AHORA),
            historial=ConsultarHistorial(pqrs, auditoria),
            terminos=ListarTerminos(configuracion, lambda: AHORA),
            solicitar_clasificacion=SolicitarClasificacion(pqrs, auditoria, 1),
        )

    def comprobar() -> None:
        if not base_responde:
            raise ConnectionError("sin conexión a 10.0.0.1:5433")

    return TestClient(crear_app(fabrica, comprobar), raise_server_exceptions=False)


@pytest.fixture
def cliente(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> TestClient:
    return _cliente(terminos, festivos)


def test_el_ejemplo_del_contrato_responde_201(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/v1/pqrs", json=EJEMPLO_REGISTRO)

    assert respuesta.status_code == 201
    assert respuesta.headers["location"] == "/api/v1/pqrs/1287"
    assert respuesta.json()["radicado"] == "RAD-2026-001287"


def test_error_400_del_contrato(cliente: TestClient) -> None:
    cuerpo = {k: v for k, v in EJEMPLO_REGISTRO.items() if k != "texto"}
    cuerpo["fechaRadicacion"] = "2026-10-30T16:00:00"

    respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json() == {
        "type": "https://radica.local/problemas/validacion",
        "title": "Datos inválidos",
        "status": 400,
        "detail": "La solicitud tiene 2 errores de validación.",
        "instance": "/api/v1/pqrs",
        "errores": [
            {"campo": "fechaRadicacion", "mensaje": "Debe ser una fecha ISO 8601 con zona horaria."},
            {"campo": "texto", "mensaje": "El texto es obligatorio."},
        ],
    }


def test_los_mensajes_no_repiten_los_valores_recibidos(cliente: TestClient) -> None:
    cuerpo = {
        **EJEMPLO_REGISTRO,
        "canal": "PALOMA_MENSAJERA",
        "peticionario": {**EJEMPLO_REGISTRO["peticionario"], "correo": "no-es-un-correo-1000000001"},
    }

    respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert respuesta.status_code == 400
    assert {e["campo"] for e in respuesta.json()["errores"]} == {"canal", "peticionario.correo"}
    for valor in ("PALOMA_MENSAJERA", "no-es-un-correo", "1000000001", "Usuario Sintético"):
        assert valor not in respuesta.text


def test_json_invalido_es_400(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/pqrs", content=b'{"canal": "DIME",', headers={"content-type": "application/json"}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == [{"campo": "cuerpo", "mensaje": "El cuerpo no es un JSON válido."}]


def test_sin_cuerpo_es_400(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/v1/pqrs")
    assert respuesta.status_code == 400
    assert respuesta.json()["errores"] == [
        {"campo": "cuerpo", "mensaje": "El cuerpo de la solicitud es obligatorio."}
    ]


@pytest.mark.parametrize(
    ("ruta", "campo"),
    [
        ("/api/v1/pqrs?tamano=101", "tamano"),
        ("/api/v1/pqrs?pagina=0", "pagina"),
        ("/api/v1/pqrs?semaforo=AZUL", "semaforo"),
        ("/api/v1/pqrs?idArea=cuatro", "idArea"),
        ("/api/v1/pqrs?estado=ABIERTA", "estado"),
        ("/api/v1/pqrs/abc", "id"),
        ("/api/v1/pqrs/0/historial", "id"),
    ],
)
def test_parametros_invalidos_son_400(cliente: TestClient, ruta: str, campo: str) -> None:
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 400
    assert respuesta.headers["content-type"] == PROBLEMA
    assert [e["campo"] for e in respuesta.json()["errores"]] == [campo]


def test_pqrs_inexistente_es_404(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/pqrs/999")
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json()["detail"] == "No existe la PQRS 999."


def test_ruta_inexistente_es_404_en_problem_details(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/no-existe")
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (404, PROBLEMA)
    assert respuesta.json()["instance"] == "/api/v1/no-existe"


def test_metodo_no_permitido(cliente: TestClient) -> None:
    respuesta = cliente.delete("/api/v1/pqrs")
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (405, PROBLEMA)


def test_error_interno_es_500_sin_detalles(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    cliente = _cliente(terminos, festivos, falla=_Falla("detalle interno: tabla pqrs, llave 0xABC"))

    respuesta = cliente.get("/api/v1/pqrs/1")

    assert (respuesta.status_code, respuesta.headers["content-type"]) == (500, PROBLEMA)
    assert respuesta.json()["detail"] == "No se pudo completar la solicitud."
    for fuga in ("detalle interno", "Traceback", "_Falla", "0xABC"):
        assert fuga not in respuesta.text


def test_sin_termino_vigente_es_500_de_configuracion(festivos: frozenset[date]) -> None:
    respuesta = _cliente((), festivos).post("/api/v1/pqrs", json=EJEMPLO_REGISTRO)

    assert (respuesta.status_code, respuesta.headers["content-type"]) == (500, PROBLEMA)
    assert respuesta.json()["type"] == "https://radica.local/problemas/configuracion"
    assert "RECLAMO" not in respuesta.text


def test_health(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    assert _cliente(terminos, festivos).get("/health").json() == {"estado": "ok"}

    respuesta = _cliente(terminos, festivos, base_responde=False).get("/health")
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (503, PROBLEMA)
    assert "10.0.0.1" not in respuesta.text


def test_el_openapi_publica_400_y_no_422(cliente: TestClient) -> None:
    esquema = cliente.get("/openapi.json").json()

    operaciones = [op for ruta in esquema["paths"].values() for op in ruta.values()]
    assert all("422" not in op["responses"] for op in operaciones)
    registro = esquema["paths"]["/api/v1/pqrs"]["post"]["responses"]
    assert set(registro) == {"201", "400"}
    assert registro["400"]["content"][PROBLEMA]["example"]["status"] == 400
    assert "HTTPValidationError" not in esquema["components"]["schemas"]
    assert {"PqrsNueva", "PqrsCreada", "PqrsDetalle", "Problema"} <= set(esquema["components"]["schemas"])


def test_el_openapi_publica_el_reintento_con_202_404_y_409(cliente: TestClient) -> None:
    esquema = cliente.get("/openapi.json").json()

    reintento = esquema["paths"]["/api/v1/pqrs/{id}/clasificaciones"]["post"]
    assert reintento["operationId"] == "solicitarClasificacionIa"
    assert set(reintento["responses"]) == {"202", "400", "404", "409"}
    assert PROBLEMA in reintento["responses"]["409"]["content"]
    assert "ClasificacionSolicitada" in esquema["components"]["schemas"]
