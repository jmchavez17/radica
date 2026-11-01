"""Lectura de la configuración desde variables de entorno.

Si hay un archivo .env en el directorio de trabajo o en uno superior, se carga
sin reemplazar las variables ya definidas; en Docker mandan las de Compose.
leer() es pura: recibe las variables y valida, para probarla sin tocar .env.
Los nombres de los precios no están en contexto.md §5: se aprobaron en la
sesión 4 (D6), con los de Claude Haiku 5.5 para prompts de hasta 100K tokens.
"""

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from dotenv import find_dotenv, load_dotenv

BYTES_LLAVE = 32
UMBRAL_AMARILLO_POR_DEFECTO = 0.5
UMBRAL_CONFIANZA_POR_DEFECTO = 0.75

PROVEEDOR_CLAUDE = "claude"
PROVEEDOR_NINGUNO = "ninguno"
PROVEEDORES_IA = (PROVEEDOR_CLAUDE, PROVEEDOR_NINGUNO)
MODELO_IA_POR_DEFECTO = "claude-haiku-5-5"
TIMEOUT_IA_POR_DEFECTO_S = 15.0
SEGUNDOS_MAXIMOS = 120.0
PRECIO_ENTRADA_POR_DEFECTO = Decimal("0.10")  # USD por millón de tokens
PRECIO_SALIDA_POR_DEFECTO = Decimal("0.50")


class ConfiguracionIncompleta(RuntimeError):
    """Falta una variable obligatoria o no es válida. El mensaje nombra la variable, nunca su valor."""


@dataclass(frozen=True)
class Configuracion:
    """Configuración de la API y del trabajador. Los secretos no salen en repr()."""

    url_base_datos: str = field(repr=False)
    llave_cifrado: bytes = field(repr=False)
    llave_hmac: bytes = field(repr=False)
    umbral_amarillo: float = UMBRAL_AMARILLO_POR_DEFECTO
    umbral_confianza: float = UMBRAL_CONFIANZA_POR_DEFECTO
    ia_proveedor: str = PROVEEDOR_NINGUNO
    ia_modelo: str = MODELO_IA_POR_DEFECTO
    ia_api_key: str | None = field(default=None, repr=False)
    ia_timeout_s: float = TIMEOUT_IA_POR_DEFECTO_S
    precio_entrada_usd_mtok: Decimal = PRECIO_ENTRADA_POR_DEFECTO
    precio_salida_usd_mtok: Decimal = PRECIO_SALIDA_POR_DEFECTO


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


def _segundos(entorno: Mapping[str, str], nombre: str, por_defecto: float) -> float:
    texto = entorno.get(nombre, "").strip()
    if not texto:
        return por_defecto
    try:
        valor = float(texto)
    except ValueError:
        valor = 0.0
    if not 0 < valor <= SEGUNDOS_MAXIMOS:
        raise ConfiguracionIncompleta(
            f"{nombre} debe ser un número de segundos mayor que 0 y hasta 120, por ejemplo 15."
        )
    return valor


def _precio(entorno: Mapping[str, str], nombre: str, por_defecto: Decimal) -> Decimal:
    texto = entorno.get(nombre, "").strip()
    if not texto:
        return por_defecto
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        valor = Decimal(-1)
    if not valor.is_finite() or valor < 0:
        raise ConfiguracionIncompleta(
            f"{nombre} debe ser un precio en USD por millón de tokens, por ejemplo 0.10."
        )
    return valor


def _proveedor(entorno: Mapping[str, str]) -> str:
    proveedor = entorno.get("IA_PROVIDER", "").strip().lower() or PROVEEDOR_NINGUNO
    if proveedor not in PROVEEDORES_IA:
        raise ConfiguracionIncompleta(
            f"IA_PROVIDER debe ser {' o '.join(PROVEEDORES_IA)}. Ver .env.example."
        )
    return proveedor


def leer(entorno: Mapping[str, str]) -> Configuracion:
    """Valida las variables; lanza ConfiguracionIncompleta con la primera que falle.

    IA_API_KEY solo es obligatoria con IA_PROVIDER=claude.
    """
    proveedor = _proveedor(entorno)
    return Configuracion(
        url_base_datos=_obligatoria(entorno, "RADICA_DB_URL"),
        llave_cifrado=_llave(entorno, "RADICA_LLAVE_CIFRADO"),
        llave_hmac=_llave(entorno, "RADICA_LLAVE_HMAC"),
        umbral_amarillo=_fraccion(entorno, "RADICA_UMBRAL_AMARILLO", UMBRAL_AMARILLO_POR_DEFECTO),
        umbral_confianza=_fraccion(entorno, "RADICA_UMBRAL_CONFIANZA", UMBRAL_CONFIANZA_POR_DEFECTO),
        ia_proveedor=proveedor,
        ia_modelo=entorno.get("IA_MODEL", "").strip() or MODELO_IA_POR_DEFECTO,
        ia_api_key=_obligatoria(entorno, "IA_API_KEY") if proveedor == PROVEEDOR_CLAUDE else None,
        ia_timeout_s=_segundos(entorno, "IA_TIMEOUT_S", TIMEOUT_IA_POR_DEFECTO_S),
        precio_entrada_usd_mtok=_precio(
            entorno, "IA_PRECIO_ENTRADA_USD_MTOK", PRECIO_ENTRADA_POR_DEFECTO
        ),
        precio_salida_usd_mtok=_precio(
            entorno, "IA_PRECIO_SALIDA_USD_MTOK", PRECIO_SALIDA_POR_DEFECTO
        ),
    )


def cargar() -> Configuracion:
    """Configuración del proceso: .env (si existe) más las variables de entorno."""
    _cargar_dotenv()
    return leer(os.environ)


def url_base_datos() -> str:
    """URL de SQLAlchemy de la base de datos (RADICA_DB_URL); la usan Alembic y las pruebas."""
    _cargar_dotenv()
    return _obligatoria(os.environ, "RADICA_DB_URL")
