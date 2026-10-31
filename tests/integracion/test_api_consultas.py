"""Consulta, bandeja, historial, términos y /health contra PostgreSQL (contexto.md 4.10).

Reloj fijo: 30 de octubre de 2026 a las 18:00, hora de Colombia. Se registran
cuatro PQRS por la API con vencimientos que dan los tres colores del semáforo.
"""

from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from radica.adaptadores.entrada.api.esquemas import EJEMPLO_REGISTRO
from radica.config import Configuracion
from radica.dominio.plazos import ZONA_COLOMBIA
from radica.main import componer

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
PROBLEMA = "application/problem+json"

# nombre: (texto, fecha de radicación). Vencimientos: vital 30-oct 17:00 (rojo),
# cita 31-oct 10:00 (amarillo), autorización 2-nov 16:00 y petición 24-nov (verdes).
PQRS = {
    "vital": ("El paciente está en riesgo vital y no lo atienden.", "2026-10-29T17:00:00-05:00"),
    "cita": ("Me cancelaron la cita tres veces este mes.", "2026-10-28T10:00:00-05:00"),
    "autorizacion": (EJEMPLO_REGISTRO["texto"], "2026-10-30T16:00:00-05:00"),
    "peticion": ("Quiero saber los horarios de la sede norte.", "2026-10-30T08:00:00-05:00"),
}


@pytest.fixture(scope="module")
def cliente(configuracion_pruebas: Configuracion) -> Iterator[TestClient]:
    with TestClient(componer(configuracion_pruebas, reloj=lambda: AHORA)) as cliente:
        yield cliente


@pytest.fixture(scope="module")
def ids(cliente: TestClient) -> dict[str, int]:
    registradas = {}
    for nombre, (texto, fecha) in PQRS.items():
        cuerpo = deepcopy(EJEMPLO_REGISTRO)
        cuerpo.update(texto=texto, fechaRadicacion=fecha)
        respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)
        assert respuesta.status_code == 201, respuesta.text
        registradas[nombre] = respuesta.json()["id"]
    return registradas


def _bandeja(cliente: TestClient, **parametros: Any) -> dict[str, Any]:
    respuesta = cliente.get("/api/v1/pqrs", params=parametros)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _nombres(pagina: dict[str, Any], ids: dict[str, int]) -> list[str]:
    por_id = {id_pqrs: nombre for nombre, id_pqrs in ids.items()}
    return [por_id[elemento["id"]] for elemento in pagina["elementos"]]


def test_consultar_el_detalle(cliente: TestClient, ids: dict[str, int]) -> None:
    respuesta = cliente.get(f"/api/v1/pqrs/{ids['autorizacion']}")

    assert respuesta.status_code == 200
    detalle = respuesta.json()
    assert detalle["radicado"] == f"RAD-2026-{ids['autorizacion']:06d}"
    assert (detalle["canal"], detalle["sede"]) == ("DIME", "Sede clínica")
    assert detalle["fechaRadicacion"] == "2026-10-30T16:00:00-05:00"
    assert detalle["textoEnmascarado"].endswith("Mi teléfono es [TELEFONO_1].")
    assert (detalle["estado"], detalle["estadoIa"]) == ("REGISTRADA", "PENDIENTE")
    assert detalle["clasificacion"]["origen"] == "REGLAS"
    assert detalle["clasificacion"]["area"] == {"id": 4, "nombre": "Autorizaciones"}
    assert detalle["vencimiento"] == {
        "fecha": "2026-11-02T16:00:00-05:00",
        "regla": "Reclamo en salud, riesgo simple: 72 horas corridas",
        "semaforo": "VERDE",
        "horasRestantes": 70.0,
    }
    assert (detalle["responsable"], detalle["posiblesDuplicados"]) == (None, [])
    for valor in ("1000000001", "Usuario Sintético Uno", "3000000000", "usuario1@ejemplo.com"):
        assert valor not in respuesta.text


def test_detalle_de_una_pqrs_que_no_existe(cliente: TestClient, ids: dict[str, int]) -> None:
    respuesta = cliente.get("/api/v1/pqrs/999999")
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (404, PROBLEMA)
    assert respuesta.json()["instance"] == "/api/v1/pqrs/999999"


def test_la_bandeja_pone_las_vencidas_primero(cliente: TestClient, ids: dict[str, int]) -> None:
    pagina = _bandeja(cliente)

    assert (pagina["pagina"], pagina["total"]) == (1, 4)
    assert _nombres(pagina, ids) == ["vital", "cita", "autorizacion", "peticion"]
    assert [e["vencimiento"]["semaforo"] for e in pagina["elementos"]] == [
        "ROJO", "AMARILLO", "VERDE", "VERDE",
    ]
    assert [e["vencimiento"]["horasRestantes"] for e in pagina["elementos"]][:3] == [-1.0, 16.0, 70.0]
    primero = pagina["elementos"][0]
    assert set(primero) == {"id", "radicado", "tipo", "nivelRiesgo", "area", "estado", "vencimiento"}
    assert (primero["tipo"], primero["nivelRiesgo"], primero["area"]) == ("RECLAMO", "VITAL", None)


def test_la_bandeja_pagina(cliente: TestClient, ids: dict[str, int]) -> None:
    segunda = _bandeja(cliente, pagina=2, tamano=2)
    assert (_nombres(segunda, ids), segunda["total"], segunda["pagina"]) == (["autorizacion", "peticion"], 4, 2)
    assert _bandeja(cliente, pagina=3, tamano=2)["elementos"] == []
    assert len(_bandeja(cliente, tamano=100)["elementos"]) == 4


@pytest.mark.parametrize(
    ("parametros", "esperados"),
    [
        ({"semaforo": "ROJO"}, ["vital"]),
        ({"semaforo": "AMARILLO"}, ["cita"]),
        ({"semaforo": "VERDE"}, ["autorizacion", "peticion"]),
        ({"tipo": "PETICION"}, ["peticion"]),
        ({"idArea": 2}, ["cita"]),
        ({"idArea": 4, "semaforo": "VERDE"}, ["autorizacion"]),
        ({"estado": "REGISTRADA", "tipo": "RECLAMO"}, ["vital", "cita", "autorizacion"]),
        ({"estado": "CERRADA"}, []),
    ],
)
def test_la_bandeja_filtra(
    cliente: TestClient, ids: dict[str, int], parametros: dict[str, Any], esperados: list[str]
) -> None:
    pagina = _bandeja(cliente, **parametros)
    assert (_nombres(pagina, ids), pagina["total"]) == (esperados, len(esperados))


@pytest.mark.parametrize("parametros", [{"tamano": 101}, {"semaforo": "AZUL"}, {"tipo": "RECLAMOS"}])
def test_la_bandeja_rechaza_filtros_invalidos(
    cliente: TestClient, ids: dict[str, int], parametros: dict[str, Any]
) -> None:
    respuesta = cliente.get("/api/v1/pqrs", params=parametros)
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (400, PROBLEMA)


def test_historial_en_orden_cronologico(cliente: TestClient, ids: dict[str, int]) -> None:
    respuesta = cliente.get(f"/api/v1/pqrs/{ids['cita']}/historial")

    assert respuesta.status_code == 200
    eventos = respuesta.json()["eventos"]
    assert [(e["origen"], e["accion"], e["campo"]) for e in eventos] == [
        ("PERSONA", "REGISTRAR", "estado"),
        ("SISTEMA", "CLASIFICAR_REGLAS", "tipo"),
        ("SISTEMA", "CLASIFICAR_REGLAS", "id_area"),
        ("SISTEMA", "CLASIFICAR_REGLAS", "nivel_riesgo"),
        ("SISTEMA", "CALCULAR_VENCIMIENTO", "fecha_vencimiento"),
    ]
    registro = eventos[0]
    assert (registro["idUsuario"], registro["valorAnterior"], registro["valorNuevo"]) == (1, None, "REGISTRADA")
    assert datetime.fromisoformat(registro["fecha"]).utcoffset() is not None
    assert (registro["modelo"], registro["versionInstrucciones"]) == (None, None)
    assert eventos[-1]["motivo"] == "Reclamo en salud, riesgo simple: 72 horas corridas"


def test_historial_de_una_pqrs_que_no_existe(cliente: TestClient, ids: dict[str, int]) -> None:
    respuesta = cliente.get("/api/v1/pqrs/999999/historial")
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (404, PROBLEMA)


def test_terminos_vigentes(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/configuracion/terminos")

    assert respuesta.status_code == 200
    terminos = respuesta.json()["terminos"]
    assert [t["id"] for t in terminos] == list(range(1, 10))
    assert terminos[8] == {
        "id": 9,
        "regimen": "SALUD",
        "tipo": "RECLAMO",
        "nivelRiesgo": "VITAL",
        "poblacion": "MENOR",
        "valor": 8,
        "unidad": "HORAS_CORRIDAS",
        "idCalendario": None,
        "fuenteNormativa": "Supersalud, Circular Externa 2026151000000007-5",
        "vigenteDesde": "2026-06-09",
        "vigenteHasta": None,
        "regla": "Reclamo en salud, riesgo vital, paciente menor de edad: 8 horas",
    }
    assert (terminos[0]["unidad"], terminos[0]["idCalendario"]) == ("DIAS_HABILES", 1)


def test_health_con_la_base_arriba(cliente: TestClient) -> None:
    respuesta = cliente.get("/health")
    assert (respuesta.status_code, respuesta.json()) == (200, {"estado": "ok"})
