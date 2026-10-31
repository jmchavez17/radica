"""Pruebas de las migraciones contra PostgreSQL 16 (docker compose up -d db).

Crean una base temporal en el mismo servidor de RADICA_DB_URL, aplican todas
las migraciones y comprueban el esquema y las semillas; al final borran la
base. La base de desarrollo no se toca. Si RADICA_DB_URL no está definida, las
pruebas se omiten y pytest las reporta como omitidas, no como exitosas.
"""

import re
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Connection, Engine, create_engine, make_url, text
from sqlalchemy.exc import DBAPIError

from radica.config import ConfiguracionIncompleta, url_base_datos
from radica.dominio.valores import (
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    Poblacion,
    Regimen,
    TipoPqrs,
    Unidad,
)

RAIZ = Path(__file__).resolve().parents[2]

TABLAS = {
    "calendario",
    "festivo",
    "termino_legal",
    "area",
    "atributo_calidad",
    "usuario",
    "peticionario",
    "pqrs",
    "llamada_ia",
    "clasificacion",
    "borrador",
    "auditoria",
    "notificacion",
}

SEMILLAS = {
    "calendario": 1,
    "festivo": 36,
    "termino_legal": 9,
    "area": 7,
    "atributo_calidad": 7,
    "usuario": 1,
}

# Cada enumeración del dominio frente a los CHECK de las columnas que la usan.
CHECKS_DEL_DOMINIO: dict[str, type[StrEnum]] = {
    "ck_pqrs_tipo": TipoPqrs,
    "ck_clasificacion_tipo": TipoPqrs,
    "ck_termino_legal_tipo_pqrs": TipoPqrs,
    "ck_atributo_calidad_tipo_sugerido": TipoPqrs,
    "ck_pqrs_nivel_riesgo": NivelRiesgo,
    "ck_clasificacion_nivel_riesgo": NivelRiesgo,
    "ck_termino_legal_nivel_riesgo": NivelRiesgo,
    "ck_pqrs_canal": Canal,
    "ck_pqrs_estado": EstadoPqrs,
    "ck_pqrs_estado_ia": EstadoIa,
    "ck_clasificacion_origen": OrigenClasificacion,
    "ck_auditoria_origen": OrigenEvento,
    "ck_termino_legal_regimen": Regimen,
    "ck_termino_legal_poblacion": Poblacion,
    "ck_termino_legal_unidad": Unidad,
}


def _alembic(url: URL) -> Config:
    config = Config(str(RAIZ / "alembic.ini"))
    config.attributes["url"] = url.render_as_string(hide_password=False)
    return config


def _tablas(conexion: Connection) -> set[str]:
    filas = conexion.execute(
        text(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    return {fila[0] for fila in filas}


@pytest.fixture(scope="module")
def url_pruebas() -> Iterator[URL]:
    try:
        url = make_url(url_base_datos())
    except ConfiguracionIncompleta as error:
        pytest.skip(str(error))
    nombre = f"{url.database}_pruebas_migracion"
    administrador = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with administrador.connect() as conexion:
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
    try:
        yield url.set(database=nombre)
    finally:
        with administrador.connect() as conexion:
            conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        administrador.dispose()


@pytest.fixture(scope="module")
def motor(url_pruebas: URL) -> Iterator[Engine]:
    command.upgrade(_alembic(url_pruebas), "head")
    motor = create_engine(url_pruebas)
    yield motor
    motor.dispose()


def test_el_servidor_es_postgresql_16(motor: Engine) -> None:
    with motor.connect() as conexion:
        version = conexion.execute(text("SHOW server_version")).scalar_one()
    assert version.startswith("16."), f"Se esperaba PostgreSQL 16 y el servidor es {version}"


def test_la_migracion_crea_las_13_tablas(motor: Engine) -> None:
    with motor.connect() as conexion:
        assert _tablas(conexion) - {"alembic_version"} == TABLAS


def test_la_migracion_carga_las_semillas(motor: Engine) -> None:
    with motor.connect() as conexion:
        conteos = {
            tabla: conexion.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()
            for tabla in SEMILLAS
        }
    assert conteos == SEMILLAS


def test_las_enumeraciones_coinciden_con_los_check(motor: Engine) -> None:
    with motor.connect() as conexion:
        definiciones = dict(
            conexion.execute(
                text(
                    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE contype = 'c' AND conname = ANY(:nombres)"
                ),
                {"nombres": list(CHECKS_DEL_DOMINIO)},
            ).all()
        )
    assert set(definiciones) == set(CHECKS_DEL_DOMINIO)
    for nombre, enumeracion in CHECKS_DEL_DOMINIO.items():
        en_base = set(re.findall(r"'([A-Z_]+)'", definiciones[nombre]))
        assert en_base == {valor.value for valor in enumeracion}, nombre


def test_auditoria_rechaza_update_delete_y_truncate(motor: Engine) -> None:
    with motor.connect() as conexion:
        transaccion = conexion.begin()
        try:
            id_peticionario = conexion.execute(
                text(
                    "INSERT INTO peticionario (documento_hash, nombre_cifrado, contacto_cifrado)"
                    " VALUES (:hash, :cifrado, :cifrado) RETURNING id_peticionario"
                ),
                {"hash": "0" * 64, "cifrado": b"\x00"},
            ).scalar_one()
            id_pqrs = conexion.execute(
                text(
                    "INSERT INTO pqrs (radicado, id_peticionario, canal, fecha_radicacion,"
                    " texto_original_cifrado, texto_enmascarado, tipo, nivel_riesgo, id_termino,"
                    " fecha_vencimiento, estado, estado_ia)"
                    " VALUES ('RAD-2026-000001', :id_peticionario, 'WEB',"
                    " '2026-10-30T16:00:00-05:00', :cifrado, 'Texto sintético de prueba',"
                    " 'PETICION', 'NO_APLICA', 1, '2026-11-24T23:59:59-05:00',"
                    " 'REGISTRADA', 'PENDIENTE') RETURNING id_pqrs"
                ),
                {"id_peticionario": id_peticionario, "cifrado": b"\x00"},
            ).scalar_one()
            conexion.execute(
                text(
                    "INSERT INTO auditoria (id_pqrs, id_usuario, origen, accion)"
                    " VALUES (:id_pqrs, 1, 'PERSONA', 'REGISTRAR')"
                ),
                {"id_pqrs": id_pqrs},
            )

            for sentencia in (
                "UPDATE auditoria SET motivo = 'cambio'",
                "DELETE FROM auditoria",
                "TRUNCATE auditoria",
            ):
                with pytest.raises(DBAPIError, match="solo inserción"):
                    with conexion.begin_nested():
                        conexion.execute(text(sentencia))

            assert conexion.execute(text("SELECT count(*) FROM auditoria")).scalar_one() == 1
        finally:
            transaccion.rollback()


def test_downgrade_a_base_y_upgrade_de_nuevo(motor: Engine, url_pruebas: URL) -> None:
    config = _alembic(url_pruebas)

    command.downgrade(config, "base")
    with motor.connect() as conexion:
        assert _tablas(conexion) == {"alembic_version"}
        funciones = conexion.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'auditoria_solo_insercion'")
        ).scalar_one()
        assert funciones == 0

    command.upgrade(config, "head")
    with motor.connect() as conexion:
        assert _tablas(conexion) - {"alembic_version"} == TABLAS
