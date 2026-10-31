"""Lectura de la configuración desde variables de entorno.

Si hay un archivo .env en el directorio de trabajo o en uno superior, se carga
sin reemplazar las variables ya definidas; en Docker mandan las de Compose.
Por ahora solo se lee RADICA_DB_URL; las demás variables de .env.example se
agregan con las piezas que las usan.
"""

import os

from dotenv import find_dotenv, load_dotenv


class ConfiguracionIncompleta(RuntimeError):
    """Falta una variable obligatoria. El mensaje nombra la variable, nunca su valor."""


def _obligatoria(nombre: str) -> str:
    load_dotenv(find_dotenv(usecwd=True), override=False)
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ConfiguracionIncompleta(
            f"Falta la variable de entorno {nombre}. Defínela en .env (ver .env.example)."
        )
    return valor


def url_base_datos() -> str:
    """URL de SQLAlchemy de la base de datos (RADICA_DB_URL)."""
    return _obligatoria("RADICA_DB_URL")
