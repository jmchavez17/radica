"""El trabajador contra PostgreSQL: registrar por la API, clasificar y consultar (contexto.md 4.9 y 4.12).

La API y el trabajador se arman con main.componer() y main.componer_trabajador()
sobre la base temporal de este módulo. El clasificador es falso: no hay red ni
clave real. Cada prueba vacía antes la cola, porque la base es del módulo.
"""

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from radica.adaptadores.entrada.api.esquemas import EJEMPLO_REGISTRO
from radica.adaptadores.salida.postgres.repositorios import PqrsRepositoryPostgres
from radica.aplicacion.puertos.clasificador import (
    ResultadoClasificacion,
    SolicitudClasificacion,
    UsoIA,
)
from radica.config import Configuracion
from radica.dominio.plazos import ZONA_COLOMBIA
from radica.dominio.valores import NivelRiesgo, TipoPqrs
from radica.main import componer, componer_trabajador

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
SUGERENCIA = ResultadoClasificacion(
    tipo=TipoPqrs.RECLAMO,
    id_atributo=2,
    id_area=4,
    nivel_riesgo=NivelRiesgo.PRIORIZADO,
    confianza=0.86,
    resumen="Paciente espera hace tres semanas la autorización de una resonancia.",
    datos_clave={"servicio": "resonancia"},
    uso=UsoIA("anthropic", "claude-haiku-5-5", 3000, 300, Decimal("0.000450"), 900),
)


class ClasificadorFijo:
    def __init__(self, resultado: ResultadoClasificacion) -> None:
        self.resultado = resultado
        self.solicitudes: list[SolicitudClasificacion] = []

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        self.solicitudes.append(solicitud)
        return self.resultado


class ClasificadorDefectuoso:
    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        raise RuntimeError("defecto de programación")


@pytest.fixture(scope="module")
def cliente(configuracion_pruebas: Configuracion) -> Iterator[TestClient]:
    with TestClient(componer(configuracion_pruebas, reloj=lambda: AHORA)) as cliente:
        yield cliente


@pytest.fixture(autouse=True)
def cola_vacia(configuracion_pruebas: Configuracion) -> None:
    trabajador = componer_trabajador(configuracion_pruebas, clasificador_ia=None)
    while trabajador.procesar_una():
        pass


def _registrar(cliente: TestClient) -> int:
    respuesta = cliente.post("/api/v1/pqrs", json=EJEMPLO_REGISTRO)
    assert respuesta.status_code == 201
    return respuesta.json()["id"]


def _eventos(cliente: TestClient, id_pqrs: int) -> list[dict]:
    return cliente.get(f"/api/v1/pqrs/{id_pqrs}/historial").json()["eventos"]


def test_el_trabajador_aplica_la_sugerencia_de_la_ia_de_punta_a_punta(
    cliente: TestClient, configuracion_pruebas: Configuracion, motor_migrado: Engine
) -> None:
    id_pqrs = _registrar(cliente)
    ia = ClasificadorFijo(SUGERENCIA)
    trabajador = componer_trabajador(configuracion_pruebas, clasificador_ia=ia)

    assert trabajador.procesar_una() is True
    assert trabajador.procesar_una() is False

    (solicitud,) = ia.solicitudes
    assert solicitud.id_pqrs == id_pqrs
    assert "[TELEFONO_1]" in solicitud.texto_enmascarado and "3000000000" not in solicitud.texto_enmascarado
    assert [area.nombre for area in solicitud.catalogo.areas][3] == "Autorizaciones"

    detalle = cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()
    assert (detalle["estado"], detalle["estadoIa"]) == ("CLASIFICADA", "COMPLETADA")
    assert detalle["clasificacion"] == {
        "origen": "IA",
        "tipo": "RECLAMO",
        "atributo": {"id": 2, "nombre": "Oportunidad"},
        "area": {"id": 4, "nombre": "Autorizaciones"},
        "nivelRiesgo": "PRIORIZADO",
        "confianza": 0.86,
        "resumen": "Paciente espera hace tres semanas la autorización de una resonancia.",
        "requiereRevision": False,
        "modelo": "claude-haiku-5-5",
        "versionInstrucciones": "clasif-v1.0",
    }
    assert detalle["vencimiento"]["fecha"] == "2026-11-01T16:00:00-05:00"
    assert detalle["vencimiento"]["regla"] == "Reclamo en salud, riesgo priorizado: 48 horas corridas"

    de_ia = [e for e in _eventos(cliente, id_pqrs) if e["accion"] == "CLASIFICAR_IA"]
    assert [(e["campo"], e["valorAnterior"], e["valorNuevo"]) for e in de_ia] == [
        ("id_atributo", None, "2"),
        ("nivel_riesgo", "SIMPLE", "PRIORIZADO"),
        ("estado", "REGISTRADA", "CLASIFICADA"),
    ]
    assert {(e["origen"], e["modelo"], e["versionInstrucciones"]) for e in de_ia} == {
        ("IA", "claude-haiku-5-5", "clasif-v1.0")
    }
    recalculo = [e for e in _eventos(cliente, id_pqrs) if e["accion"] == "CALCULAR_VENCIMIENTO"][-1]
    assert (recalculo["valorAnterior"], recalculo["valorNuevo"]) == (
        "2026-11-02T16:00:00-05:00", "2026-11-01T16:00:00-05:00",
    )
    assert recalculo["modelo"] is None

    with motor_migrado.connect() as conexion:
        llamadas = conexion.execute(
            text("SELECT intento, resultado, tokens_entrada, costo_usd FROM llamada_ia WHERE id_pqrs = :id"),
            {"id": id_pqrs},
        ).all()
    assert [tuple(fila) for fila in llamadas] == [(1, "OK", 3000, Decimal("0.000450"))]


def test_dos_trabajadores_no_toman_la_misma_pqrs(cliente: TestClient, motor_migrado: Engine) -> None:
    primera, segunda = _registrar(cliente), _registrar(cliente)

    with motor_migrado.connect() as uno, motor_migrado.connect() as otro:
        with uno.begin(), otro.begin():
            tomada = PqrsRepositoryPostgres(uno).pendientes_de_ia(1)
            assert tomada == [primera]
            # SKIP LOCKED: el segundo no espera ni repite, toma la siguiente.
            assert PqrsRepositoryPostgres(otro).pendientes_de_ia(1) == [segunda]
            assert primera not in PqrsRepositoryPostgres(otro).pendientes_de_ia(10)


def test_un_error_inesperado_deja_fallida_y_no_se_vuelve_a_tomar(
    cliente: TestClient, configuracion_pruebas: Configuracion
) -> None:
    id_pqrs = _registrar(cliente)
    trabajador = componer_trabajador(configuracion_pruebas, clasificador_ia=ClasificadorDefectuoso())

    assert trabajador.procesar_una() is True
    assert trabajador.procesar_una() is False

    detalle = cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()
    assert (detalle["estado"], detalle["estadoIa"]) == ("REQUIERE_REVISION", "FALLIDA")
    assert detalle["clasificacion"]["origen"] == "REGLAS"
    ultimo = _eventos(cliente, id_pqrs)[-1]
    assert (ultimo["accion"], ultimo["motivo"]) == (
        "IA_FALLIDA", "Error interno al clasificar. Sigue vigente la clasificación por reglas.",
    )


def test_con_ia_ninguno_la_pqrs_queda_omitida(cliente: TestClient, configuracion_pruebas: Configuracion) -> None:
    id_pqrs = _registrar(cliente)
    assert configuracion_pruebas.ia_proveedor == "ninguno"

    assert componer_trabajador(configuracion_pruebas).procesar_una() is True

    detalle = cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()
    assert (detalle["estado"], detalle["estadoIa"]) == ("REQUIERE_REVISION", "OMITIDA")
    ultimos = _eventos(cliente, id_pqrs)[-2:]
    assert [(e["campo"], e["valorAnterior"], e["valorNuevo"]) for e in ultimos] == [
        ("estado_ia", "PENDIENTE", "OMITIDA"),
        ("estado", "REGISTRADA", "REQUIERE_REVISION"),
    ]
    assert {(e["accion"], e["motivo"]) for e in ultimos} == {("IA_OMITIDA", "IA desactivada por configuración")}


def test_verifica_con_los_datos_del_peticionario_descifrados_de_la_base(
    cliente: TestClient, configuracion_pruebas: Configuracion, motor_migrado: Engine
) -> None:
    id_pqrs = _registrar(cliente)
    # Simula un defecto del enmascaramiento al registrar: el nombre quedó a la vista.
    with motor_migrado.begin() as conexion:
        conexion.execute(
            text("UPDATE pqrs SET texto_enmascarado = :texto WHERE id_pqrs = :id"),
            {"texto": "Soy Usuario Sintético Uno y no me han dado la autorización.", "id": id_pqrs},
        )
    espia = ClasificadorFijo(SUGERENCIA)

    componer_trabajador(configuracion_pruebas, clasificador_ia=espia).procesar_una()

    assert espia.solicitudes == []
    detalle = cliente.get(f"/api/v1/pqrs/{id_pqrs}").json()
    assert detalle["estadoIa"] == "OMITIDA"
    assert _eventos(cliente, id_pqrs)[-1]["motivo"] == (
        "Enmascaramiento no verificado: quedan datos de tipo NOMBRE. No se llamó a la IA."
    )
