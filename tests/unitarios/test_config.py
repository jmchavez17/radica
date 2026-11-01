"""Lectura de la configuración (contexto.md 5). Usa valores generados aquí; no lee .env."""

import base64
import os
from decimal import Decimal

import pytest

from radica.config import ConfiguracionIncompleta, leer

URL = "postgresql+psycopg://radica:secreto-de-prueba@127.0.0.1:5433/radica"
LLAVE_CIFRADO = base64.b64encode(os.urandom(32)).decode()
LLAVE_HMAC = base64.b64encode(os.urandom(32)).decode()


def _entorno(**cambios: str) -> dict[str, str]:
    entorno = {
        "RADICA_DB_URL": URL,
        "RADICA_LLAVE_CIFRADO": LLAVE_CIFRADO,
        "RADICA_LLAVE_HMAC": LLAVE_HMAC,
    }
    entorno.update(cambios)
    return entorno


def test_lee_la_configuracion_completa() -> None:
    configuracion = leer(_entorno(RADICA_UMBRAL_AMARILLO="0.4"))

    assert configuracion.url_base_datos == URL
    assert configuracion.llave_cifrado == base64.b64decode(LLAVE_CIFRADO)
    assert configuracion.llave_hmac == base64.b64decode(LLAVE_HMAC)
    assert configuracion.umbral_amarillo == 0.4


def test_el_umbral_amarillo_por_defecto_es_0_5() -> None:
    assert leer(_entorno()).umbral_amarillo == 0.5


def test_repr_no_muestra_secretos() -> None:
    texto = repr(leer(_entorno()))
    assert "secreto-de-prueba" not in texto
    assert LLAVE_CIFRADO not in texto
    assert "llave" not in texto


@pytest.mark.parametrize("variable", ["RADICA_DB_URL", "RADICA_LLAVE_CIFRADO", "RADICA_LLAVE_HMAC"])
@pytest.mark.parametrize("valor", ["", "   "])
def test_no_arranca_sin_una_variable_obligatoria(variable: str, valor: str) -> None:
    entorno = _entorno()
    entorno[variable] = valor
    with pytest.raises(ConfiguracionIncompleta, match=f"Falta la variable de entorno {variable}"):
        leer(entorno)


def test_sin_la_variable_tambien_falla() -> None:
    entorno = _entorno()
    del entorno["RADICA_LLAVE_HMAC"]
    with pytest.raises(ConfiguracionIncompleta, match="RADICA_LLAVE_HMAC"):
        leer(entorno)


@pytest.mark.parametrize(
    "valor",
    ["no-es-base64!", base64.b64encode(os.urandom(16)).decode(), base64.b64encode(os.urandom(33)).decode()],
    ids=["no-base64", "16-bytes", "33-bytes"],
)
def test_la_llave_debe_tener_32_bytes_y_el_mensaje_no_la_muestra(valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta) as error:
        leer(_entorno(RADICA_LLAVE_CIFRADO=valor))

    assert "RADICA_LLAVE_CIFRADO" in str(error.value)
    assert valor not in str(error.value)


@pytest.mark.parametrize("valor", ["0", "1", "1.5", "medio"])
def test_el_umbral_amarillo_debe_estar_entre_0_y_1(valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta, match="RADICA_UMBRAL_AMARILLO"):
        leer(_entorno(RADICA_UMBRAL_AMARILLO=valor))


# --- Configuración de la IA (contexto.md §5; precios aprobados en la sesión 4, D6) ---

CLAVE_FALSA = "clave-falsa-de-prueba"


def test_sin_variables_de_ia_opera_sin_proveedor() -> None:
    configuracion = leer(_entorno())

    assert configuracion.ia_proveedor == "ninguno"
    assert configuracion.ia_modelo == "claude-haiku-5-5"
    assert configuracion.ia_api_key is None
    assert configuracion.ia_timeout_s == 15
    assert configuracion.umbral_confianza == 0.75
    assert configuracion.precio_entrada_usd_mtok == Decimal("0.10")
    assert configuracion.precio_salida_usd_mtok == Decimal("0.50")


def test_lee_la_configuracion_de_claude() -> None:
    configuracion = leer(
        _entorno(
            IA_PROVIDER=" Claude ",
            IA_MODEL="claude-haiku-5-5",
            IA_API_KEY=CLAVE_FALSA,
            IA_TIMEOUT_S="20",
            RADICA_UMBRAL_CONFIANZA="0.8",
            IA_PRECIO_ENTRADA_USD_MTOK="0.25",
            IA_PRECIO_SALIDA_USD_MTOK="1.25",
        )
    )

    assert configuracion.ia_proveedor == "claude"
    assert configuracion.ia_api_key == CLAVE_FALSA
    assert configuracion.ia_timeout_s == 20
    assert configuracion.umbral_confianza == 0.8
    assert configuracion.precio_entrada_usd_mtok == Decimal("0.25")
    assert configuracion.precio_salida_usd_mtok == Decimal("1.25")


@pytest.mark.parametrize("valor", ["", "   "])
def test_con_claude_la_clave_es_obligatoria(valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta, match="Falta la variable de entorno IA_API_KEY"):
        leer(_entorno(IA_PROVIDER="claude", IA_API_KEY=valor))


def test_con_ninguno_la_clave_no_se_usa() -> None:
    assert leer(_entorno(IA_PROVIDER="ninguno", IA_API_KEY=CLAVE_FALSA)).ia_api_key is None


def test_repr_no_muestra_la_clave_de_la_ia() -> None:
    texto = repr(leer(_entorno(IA_PROVIDER="claude", IA_API_KEY=CLAVE_FALSA)))
    assert CLAVE_FALSA not in texto
    assert "api_key" not in texto


def test_el_proveedor_debe_ser_claude_o_ninguno() -> None:
    with pytest.raises(ConfiguracionIncompleta, match="IA_PROVIDER debe ser claude o ninguno") as error:
        leer(_entorno(IA_PROVIDER="gemini"))
    assert "gemini" not in str(error.value)


@pytest.mark.parametrize("valor", ["0", "-1", "121", "quince"])
def test_el_timeout_debe_ser_positivo_y_razonable(valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta, match="IA_TIMEOUT_S"):
        leer(_entorno(IA_TIMEOUT_S=valor))


@pytest.mark.parametrize("valor", ["0", "1", "alta"])
def test_el_umbral_de_confianza_debe_estar_entre_0_y_1(valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta, match="RADICA_UMBRAL_CONFIANZA"):
        leer(_entorno(RADICA_UMBRAL_CONFIANZA=valor))


@pytest.mark.parametrize("variable", ["IA_PRECIO_ENTRADA_USD_MTOK", "IA_PRECIO_SALIDA_USD_MTOK"])
@pytest.mark.parametrize("valor", ["-0.1", "gratis", "NaN", "Infinity"])
def test_el_precio_debe_ser_un_numero_no_negativo(variable: str, valor: str) -> None:
    with pytest.raises(ConfiguracionIncompleta, match=variable):
        leer(_entorno(**{variable: valor}))
