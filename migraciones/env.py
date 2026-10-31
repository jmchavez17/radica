"""Entorno de Alembic para Radica.

La URL sale de RADICA_DB_URL (radica.config). Quien invoque Alembic desde código
puede pasar otra en config.attributes["url"]; lo usa la prueba de migración.
No hay metadatos de modelos: el esquema se escribe a mano en cada migración
(regla 5: nada de creación automática de tablas desde los modelos).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from radica.config import url_base_datos

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _url() -> str:
    return config.attributes.get("url") or url_base_datos()


def ejecutar_sin_conexion() -> None:
    """Genera el SQL sin conectarse (alembic upgrade --sql)."""
    context.configure(
        url=_url(),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_con_conexion() -> None:
    motor = create_engine(_url(), poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            context.configure(connection=conexion, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        motor.dispose()


if context.is_offline_mode():
    ejecutar_sin_conexion()
else:
    ejecutar_con_conexion()
