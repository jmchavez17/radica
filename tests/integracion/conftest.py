"""Base temporal para las pruebas de integración de repositorios y API.

Cada módulo de prueba crea su propia base en el servidor de RADICA_DB_URL
(<base>_pruebas_<módulo>), le aplica las migraciones y la borra al terminar.
No se vacía con TRUNCATE porque la auditoría es de solo inserción. Si
RADICA_DB_URL no está definida, las pruebas se omiten.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text

from radica.adaptadores.salida.postgres.repositorios import crear_motor
from radica.config import Configuracion, ConfiguracionIncompleta, url_base_datos

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def configuracion_pruebas(motor_migrado: Engine) -> Configuracion:
    """Configuración sobre la base temporal, con llaves generadas aquí (nunca las del .env)."""
    return Configuracion(
        url_base_datos=motor_migrado.url.render_as_string(hide_password=False),
        llave_cifrado=os.urandom(32),
        llave_hmac=os.urandom(32),
        umbral_amarillo=0.5,
    )


@pytest.fixture(scope="module")
def motor_migrado(request: pytest.FixtureRequest) -> Iterator[Engine]:
    try:
        url = make_url(url_base_datos())
    except ConfiguracionIncompleta as error:
        pytest.skip(str(error))
    modulo = request.module.__name__.rsplit(".", 1)[-1].removeprefix("test_")
    nombre = f"{url.database}_pruebas_{modulo}"
    administrador = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with administrador.connect() as conexion:
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
    url_pruebas = url.set(database=nombre)
    config = Config(str(RAIZ / "alembic.ini"))
    config.attributes["url"] = url_pruebas.render_as_string(hide_password=False)
    motor = crear_motor(url_pruebas.render_as_string(hide_password=False))
    try:
        command.upgrade(config, "head")
        yield motor
    finally:
        motor.dispose()
        with administrador.connect() as conexion:
            conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        administrador.dispose()
