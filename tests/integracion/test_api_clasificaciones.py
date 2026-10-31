"""POST /api/v1/pqrs/{id}/clasificaciones contra PostgreSQL (contexto.md 4.10, 4.11 y 4.12).

El reintento deja la PQRS PENDIENTE; el trabajador (con un clasificador falso,
sin red) la vuelve a clasificar sin duplicar la clasificación vigente.
"""

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from radica.adaptadores.entrada.api.esquemas import EJEMPLO_REGISTRO
from radica.aplicacion.puertos.clasificador import ResultadoClasificacion, SolicitudClasificacion, UsoIA
from radica.config import Configuracion
from radica.dominio.plazos import ZONA_COLOMBIA
from radica.dominio.valores import NivelRiesgo, TipoPqrs
from radica.main import componer, componer_trabajador

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
PROBLEMA = "application/problem+json"


class ClasificadorFijo:
    def __init__(self, nivel: NivelRiesgo) -> None:
        self.nivel = nivel

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        return ResultadoClasificacion(
            TipoPqrs.RECLAMO, 2, 4, self.nivel, 0.9, resumen="Espera la autorización de una resonancia.",
            uso=UsoIA("anthropic", "claude-haiku-5-5", 2500, 200, Decimal("0.000350"), 700),
        )


@pytest.fixture(scope="module")
def cliente(configuracion_pruebas: Configuracion) -> Iterator[TestClient]:
    with TestClient(componer(configuracion_pruebas, reloj=lambda: AHORA)) as cliente:
        yield cliente


def _registrar(cliente: TestClient) -> int:
    return cliente.post("/api/v1/pqrs", json=EJEMPLO_REGISTRO).json()["id"]


def _procesar(configuracion: Configuracion, nivel: NivelRiesgo | None) -> None:
    clasificador = ClasificadorFijo(nivel) if nivel is not None else None
    trabajador = componer_trabajador(configuracion, clasificador_ia=clasificador)
    while trabajador.procesar_una():
        pass


def test_reintento_202_y_el_trabajador_reclasifica_sin_duplicar(
    cliente: TestClient, configuracion_pruebas: Configuracion, motor_migrado: Engine
) -> None:
    id_pqrs = _registrar(cliente)
    _procesar(configuracion_pruebas, nivel=None)  # IA desactivada: OMITIDA
    assert cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()["estadoIa"] == "OMITIDA"

    respuesta = cliente.post(f"/api/v1/pqrs/{id_pqrs}/clasificaciones")

    assert respuesta.status_code == 202
    assert respuesta.json() == {"id": id_pqrs, "estadoIa": "PENDIENTE"}
    reintento = cliente.get(f"/api/v1/pqrs/{id_pqrs}/historial").json()["eventos"][-1]
    assert {k: reintento[k] for k in ("origen", "accion", "idUsuario", "campo", "valorAnterior", "valorNuevo")} == {
        "origen": "PERSONA",
        "accion": "REINTENTO_IA",
        "idUsuario": 1,
        "campo": "estado_ia",
        "valorAnterior": "OMITIDA",
        "valorNuevo": "PENDIENTE",
    }

    _procesar(configuracion_pruebas, NivelRiesgo.PRIORIZADO)
    # Una segunda sugerencia, ahora VITAL: reemplaza a la anterior sin duplicar la vigente.
    assert cliente.post(f"/api/v1/pqrs/{id_pqrs}/clasificaciones").status_code == 202
    _procesar(configuracion_pruebas, NivelRiesgo.VITAL)

    detalle = cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()
    assert (detalle["estadoIa"], detalle["clasificacion"]["nivelRiesgo"]) == ("COMPLETADA", "VITAL")
    assert detalle["vencimiento"]["fecha"] == "2026-10-31T16:00:00-05:00"
    with motor_migrado.connect() as conexion:
        filas = conexion.execute(
            text("SELECT origen, nivel_riesgo, vigente FROM clasificacion WHERE id_pqrs = :id ORDER BY id_clasificacion"),
            {"id": id_pqrs},
        ).all()
    assert [tuple(fila) for fila in filas] == [
        ("REGLAS", "SIMPLE", False), ("IA", "PRIORIZADO", False), ("IA", "VITAL", True),
    ]


def test_reintento_409_si_ya_esta_pendiente(cliente: TestClient) -> None:
    id_pqrs = _registrar(cliente)  # recién registrada: PENDIENTE

    respuesta = cliente.post(f"/api/v1/pqrs/{id_pqrs}/clasificaciones")

    assert (respuesta.status_code, respuesta.headers["content-type"]) == (409, PROBLEMA)
    assert respuesta.json() == {
        "type": "https://radica.local/problemas/conflicto",
        "title": "Operación no permitida",
        "status": 409,
        "detail": "La PQRS ya está pendiente de clasificación con IA.",
        "instance": f"/api/v1/pqrs/{id_pqrs}/clasificaciones",
    }


@pytest.mark.parametrize("estado", ["RESPONDIDA", "CERRADA"])
def test_reintento_409_si_esta_respondida_o_cerrada(
    cliente: TestClient, configuracion_pruebas: Configuracion, motor_migrado: Engine, estado: str
) -> None:
    id_pqrs = _registrar(cliente)
    _procesar(configuracion_pruebas, nivel=None)
    with motor_migrado.begin() as conexion:
        conexion.execute(text("UPDATE pqrs SET estado = :estado WHERE id_pqrs = :id"), {"estado": estado, "id": id_pqrs})
    eventos = len(cliente.get(f"/api/v1/pqrs/{id_pqrs}/historial").json()["eventos"])

    respuesta = cliente.post(f"/api/v1/pqrs/{id_pqrs}/clasificaciones")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == f"La PQRS está en estado {estado}: ya no se puede clasificar de nuevo."
    assert cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()["estadoIa"] == "OMITIDA"
    assert len(cliente.get(f"/api/v1/pqrs/{id_pqrs}/historial").json()["eventos"]) == eventos


def test_reintento_404_y_400(cliente: TestClient) -> None:
    no_existe = cliente.post("/api/v1/pqrs/999999/clasificaciones")
    assert (no_existe.status_code, no_existe.json()["detail"]) == (404, "No existe la PQRS 999999.")
    assert cliente.post("/api/v1/pqrs/0/clasificaciones").status_code == 400
    assert cliente.post("/api/v1/pqrs/abc/clasificaciones").status_code == 400
