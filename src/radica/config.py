"""Lectura de la configuración desde variables de entorno.

Si hay un archivo .env en el directorio de trabajo o en uno superior, se carga
sin reemplazar las variables ya definidas; en Docker mandan las de Compose.
leer() es pura: recibe las variables y valida, para probarla sin tocar .env.
Las variables de la IA se agregan con las piezas que las usan.
"""

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from dotenv import find_dotenv, load_dotenv

BYTES_LLAVE = 32
UMBRAL_AMARILLO_POR_DEFECTO = 0.5


class ConfiguracionIncompleta(RuntimeError):
    """Falta una variable obligatoria o no es válida. El mensaje nombra la variable, nunca su valor."""


@dataclass(frozen=True)
class Configuracion:
    """Configuración de la API. Los secretos no salen en repr()."""

    url_base_datos: str = field(repr=False)
    llave_cifrado: bytes = field(repr=False)
    llave_hmac: bytes = field(repr=False)
    umbral_amarillo: float = UMBRAL_AMARILLO_POR_DEFECTO


def _cargar_dotenv() -> None:
    load_dotenv(find_dotenv(usecwd=True), override=False)


def _obligatoria(entorno: Mapping[str, str], nombre: str) -> str:
    valor = entorno.get(nombre, "").strip()
    if not valor:
        raise ConfiguracionIncompleta(
            f"Falta la variable de entorno {nombre}. Defínela en .env (ver .env.example)."
        )
    return valor


def _llave(entorno: Mapping[str, str], nombre: str) -> bytes:
    try:
        llave = base64.b64decode(_obligatoria(entorno, nombre), validate=True)
    except binascii.Error:
        llave = b""
    if len(llave) != BYTES_LLAVE:
        raise ConfiguracionIncompleta(
            f"{nombre} debe tener {BYTES_LLAVE} bytes en base64. Genérala como indica .env.example."
        )
    return llave


def _fraccion(entorno: Mapping[str, str], nombre: str, por_defecto: float) -> float:
    texto = entorno.get(nombre, "").strip()
    if not texto:
        return por_defecto
    try:
        valor = float(texto)
    except ValueError:
        valor = -1.0
    if not 0 < valor < 1:
        raise ConfiguracionIncompleta(f"{nombre} debe ser un número entre 0 y 1, por ejemplo 0.5.")
    return valor


def leer(entorno: Mapping[str, str]) -> Configuracion:
    """Valida las variables de la API; lanza ConfiguracionIncompleta con la primera que falle."""
    return Configuracion(
        url_base_datos=_obligatoria(entorno, "RADICA_DB_URL"),
        llave_cifrado=_llave(entorno, "RADICA_LLAVE_CIFRADO"),
        llave_hmac=_llave(entorno, "RADICA_LLAVE_HMAC"),
        umbral_amarillo=_fraccion(entorno, "RADICA_UMBRAL_AMARILLO", UMBRAL_AMARILLO_POR_DEFECTO),
    )


def cargar() -> Configuracion:
    """Configuración del proceso: .env (si existe) más las variables de entorno."""
    _cargar_dotenv()
    return leer(os.environ)


def url_base_datos() -> str:
    """URL de SQLAlchemy de la base de datos (RADICA_DB_URL); la usan Alembic y las pruebas."""
    _cargar_dotenv()
    return _obligatoria(os.environ, "RADICA_DB_URL")
