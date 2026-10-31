"""POST /api/v1/pqrs contra PostgreSQL (contexto.md 4.1 a 4.8, 4.11 y 4.12; HU-01).

La API se arma con main.componer() sobre una base temporal, llaves de prueba
y un reloj fijo: el 30 de octubre de 2026 a las 18:00, hora de Colombia.
"""

import hashlib
import hmac
import json
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from radica.adaptadores.entrada.api.esquemas import EJEMPLO_REGISTRO
from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.config import Configuracion
from radica.dominio.plazos import ZONA_COLOMBIA
from radica.main import componer

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
PROBLEMA = "application/problem+json"
DATOS_PERSONALES = ("1000000001", "Usuario Sintético Uno", "3000000000", "usuario1@ejemplo.com")
TABLAS = ("peticionario", "pqrs", "clasificacion", "auditoria")


@pytest.fixture(scope="module")
def cliente(configuracion_pruebas: Configuracion) -> Iterator[TestClient]:
    with TestClient(componer(configuracion_pruebas, reloj=lambda: AHORA)) as cliente:
        yield cliente


@pytest.fixture(scope="module")
def cifrador(configuracion_pruebas: Configuracion) -> CifradorAesGcm:
    return CifradorAesGcm(configuracion_pruebas.llave_cifrado, configuracion_pruebas.llave_hmac)


def _conteos(motor: Engine) -> dict[str, int]:
    with motor.connect() as conexion:
        return {t: conexion.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in TABLAS}


def _cuerpo(**cambios: Any) -> dict[str, Any]:
    cuerpo = deepcopy(EJEMPLO_REGISTRO)
    peticionario = cambios.pop("peticionario", {})
    cuerpo.update(cambios)
    cuerpo["peticionario"].update(peticionario)
    return cuerpo


def test_registra_el_ejemplo_del_contrato(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/v1/pqrs", json=_cuerpo())

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert respuesta.headers["location"] == f"/api/v1/pqrs/{cuerpo['id']}"
    assert cuerpo == {
        "id": cuerpo["id"],
        "radicado": f"RAD-2026-{cuerpo['id']:06d}",
        "estado": "REGISTRADA",
        "estadoIa": "PENDIENTE",
        "clasificacionProvisional": {
            "origen": "REGLAS",
            "tipo": "RECLAMO",
            "atributo": None,
            "area": {"id": 4, "nombre": "Autorizaciones"},
            "nivelRiesgo": "SIMPLE",
            "confianza": 0.5,
            "resumen": None,
            "requiereRevision": False,
            "modelo": None,
            "versionInstrucciones": None,
        },
        "vencimiento": {
            "fecha": "2026-11-02T16:00:00-05:00",
            "regla": "Reclamo en salud, riesgo simple: 72 horas corridas",
            "semaforo": "VERDE",
            "horasRestantes": 70.0,
        },
        "posiblesDuplicados": [],
    }
    for valor in DATOS_PERSONALES:
        assert valor not in respuesta.text


def test_guarda_cifrado_lo_del_peticionario_y_enmascarado_el_texto(
    cliente: TestClient,
    motor_migrado: Engine,
    cifrador: CifradorAesGcm,
    configuracion_pruebas: Configuracion,
) -> None:
    id_pqrs = cliente.post("/api/v1/pqrs", json=_cuerpo()).json()["id"]

    with motor_migrado.connect() as conexion:
        fila = conexion.execute(
            text(
                "SELECT p.texto_enmascarado, p.texto_original_cifrado, p.estado_ia, pe.documento_hash,"
                " pe.nombre_cifrado, pe.contacto_cifrado FROM pqrs p"
                " JOIN peticionario pe USING (id_peticionario) WHERE p.id_pqrs = :id"
            ),
            {"id": id_pqrs},
        ).one()

    assert fila.texto_enmascarado.endswith("Mi teléfono es [TELEFONO_1].")
    assert "3000000000" not in fila.texto_enmascarado
    assert cifrador.descifrar(bytes(fila.texto_original_cifrado)) == EJEMPLO_REGISTRO["texto"]
    assert fila.estado_ia == "PENDIENTE"
    huella = hmac.new(configuracion_pruebas.llave_hmac, b"CC:1000000001", hashlib.sha256).hexdigest()
    assert fila.documento_hash == huella
    assert cifrador.descifrar(bytes(fila.nombre_cifrado)) == "Usuario Sintético Uno"
    assert json.loads(cifrador.descifrar(bytes(fila.contacto_cifrado))) == {
        "telefono": "3000000000",
        "correo": "usuario1@ejemplo.com",
    }
    for columna in (fila.nombre_cifrado, fila.contacto_cifrado, fila.texto_original_cifrado):
        assert b"Usuario" not in bytes(columna) and b"3000000000" not in bytes(columna)


def test_el_mismo_documento_reutiliza_al_peticionario_sin_sobrescribirlo(
    cliente: TestClient, motor_migrado: Engine, cifrador: CifradorAesGcm
) -> None:
    documento = {"numeroDocumento": "1000000099", "nombre": "Primer Nombre Sintético"}
    primera = cliente.post("/api/v1/pqrs", json=_cuerpo(peticionario=documento)).json()
    otro = {**documento, "nombre": "Segundo Nombre Sintético"}
    segunda = cliente.post("/api/v1/pqrs", json=_cuerpo(peticionario=otro)).json()

    assert segunda["radicado"] != primera["radicado"]
    with motor_migrado.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT DISTINCT pe.id_peticionario, pe.nombre_cifrado FROM pqrs p"
                " JOIN peticionario pe USING (id_peticionario) WHERE p.id_pqrs IN (:a, :b)"
            ),
            {"a": primera["id"], "b": segunda["id"]},
        ).all()
    assert len(filas) == 1
    assert cifrador.descifrar(bytes(filas[0].nombre_cifrado)) == "Primer Nombre Sintético"


def test_deja_los_eventos_de_auditoria(cliente: TestClient, motor_migrado: Engine) -> None:
    id_pqrs = cliente.post("/api/v1/pqrs", json=_cuerpo()).json()["id"]

    with motor_migrado.connect() as conexion:
        eventos = conexion.execute(
            text(
                "SELECT origen, accion, id_usuario, campo, valor_nuevo FROM auditoria"
                " WHERE id_pqrs = :id ORDER BY id_evento"
            ),
            {"id": id_pqrs},
        ).all()

    assert [tuple(e) for e in eventos] == [
        ("PERSONA", "REGISTRAR", 1, "estado", "REGISTRADA"),
        ("SISTEMA", "CLASIFICAR_REGLAS", None, "tipo", "RECLAMO"),
        ("SISTEMA", "CLASIFICAR_REGLAS", None, "id_area", "4"),
        ("SISTEMA", "CLASIFICAR_REGLAS", None, "nivel_riesgo", "SIMPLE"),
        ("SISTEMA", "CALCULAR_VENCIMIENTO", None, "fecha_vencimiento", "2026-11-02T16:00:00-05:00"),
    ]


def test_reclamo_vital_de_un_menor_vence_en_8_horas(cliente: TestClient) -> None:
    cuerpo = _cuerpo(
        texto="Mi hijo está en riesgo vital y no lo atienden en urgencias.", pacienteMenorDeEdad=True
    )

    respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert respuesta.status_code == 201
    assert respuesta.json()["vencimiento"] == {
        "fecha": "2026-10-31T00:00:00-05:00",
        "regla": "Reclamo en salud, riesgo vital, paciente menor de edad: 8 horas",
        "semaforo": "VERDE",
        "horasRestantes": 6.0,
    }


def test_opcionales_ausentes(cliente: TestClient) -> None:
    cuerpo = _cuerpo(texto="Quiero saber los horarios de la sede norte.")
    del cuerpo["sede"], cuerpo["pacienteMenorDeEdad"]
    del cuerpo["peticionario"]["telefono"], cuerpo["peticionario"]["correo"]

    respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert respuesta.status_code == 201
    assert respuesta.json()["vencimiento"]["regla"] == "Petición: 15 días hábiles"


INVALIDOS = [
    ("sin-canal", {"canal": None}, "canal", "El canal es obligatorio."),
    ("canal-desconocido", {"canal": "FAX"}, "canal", None),
    ("sede-61", {"sede": "s" * 61}, "sede", "Debe tener máximo 60 caracteres."),
    ("sin-fecha", {"fechaRadicacion": None}, "fechaRadicacion", "La fecha de radicación es obligatoria."),
    ("fecha-sin-zona", {"fechaRadicacion": "2026-10-30T16:00:00"}, "fechaRadicacion", None),
    ("fecha-sin-hora", {"fechaRadicacion": "2026-10-30"}, "fechaRadicacion", None),
    ("fecha-futura", {"fechaRadicacion": "2026-10-30T18:00:01-05:00"}, "fechaRadicacion",
     "No puede ser posterior al momento del registro."),
    ("sin-texto", {"texto": None}, "texto", "El texto es obligatorio."),
    ("texto-de-espacios", {"texto": "            "}, "texto", "El texto es obligatorio."),
    ("texto-9", {"texto": "123456789"}, "texto", "Debe tener al menos 10 caracteres."),
    ("texto-10001", {"texto": "a" * 10001}, "texto", "Debe tener máximo 10000 caracteres."),
    ("menor-no-booleano", {"pacienteMenorDeEdad": "quizás"}, "pacienteMenorDeEdad", None),
    ("sin-peticionario", {"peticionario": None}, "peticionario", None),
    ("tipo-documento", {"peticionario": {"tipoDocumento": "NIT"}}, "peticionario.tipoDocumento", None),
    ("documento-21", {"peticionario": {"numeroDocumento": "1" * 21}}, "peticionario.numeroDocumento",
     "Debe tener máximo 20 caracteres."),
    ("sin-nombre", {"peticionario": {"nombre": ""}}, "peticionario.nombre", "El nombre es obligatorio."),
    ("nombre-151", {"peticionario": {"nombre": "n" * 151}}, "peticionario.nombre",
     "Debe tener máximo 150 caracteres."),
    ("telefono-21", {"peticionario": {"telefono": "3" * 21}}, "peticionario.telefono",
     "Debe tener máximo 20 caracteres."),
    ("correo", {"peticionario": {"correo": "usuario1@ejemplo"}}, "peticionario.correo",
     "Debe ser un correo electrónico válido."),
]


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"), [caso[1:] for caso in INVALIDOS], ids=[caso[0] for caso in INVALIDOS]
)
def test_datos_invalidos_responden_400_sin_guardar(
    cliente: TestClient, motor_migrado: Engine, cambios: dict[str, Any], campo: str, mensaje: str | None
) -> None:
    cuerpo = _cuerpo()
    for clave, valor in cambios.items():  # None quita el campo; un dict cambia el peticionario
        if valor is None:
            del cuerpo[clave]
        elif isinstance(valor, dict):
            cuerpo[clave].update(valor)
        else:
            cuerpo[clave] = valor
    antes = _conteos(motor_migrado)

    respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.headers["content-type"] == PROBLEMA
    errores = respuesta.json()["errores"]
    assert [error["campo"] for error in errores] == [campo]
    if mensaje is not None:
        assert errores[0]["mensaje"] == mensaje
    assert _conteos(motor_migrado) == antes


def test_un_fallo_a_mitad_del_registro_no_deja_nada(
    configuracion_pruebas: Configuracion, motor_migrado: Engine
) -> None:
    # Con un usuario actor que no existe, el primer evento de auditoría viola su llave
    # foránea después de insertar el peticionario, la PQRS y la clasificación.
    app = componer(configuracion_pruebas, reloj=lambda: AHORA, id_usuario_actor=999)
    cuerpo = _cuerpo(peticionario={"numeroDocumento": "1000000777"})
    antes = _conteos(motor_migrado)

    with TestClient(app, raise_server_exceptions=False) as cliente:
        respuesta = cliente.post("/api/v1/pqrs", json=cuerpo)

    assert (respuesta.status_code, respuesta.headers["content-type"]) == (500, PROBLEMA)
    assert respuesta.json()["detail"] == "No se pudo completar la solicitud."
    assert "auditoria" not in respuesta.text and "1000000777" not in respuesta.text
    assert _conteos(motor_migrado) == antes
