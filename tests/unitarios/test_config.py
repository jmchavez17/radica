"""Lectura de la configuración (contexto.md 5). Usa valores generados aquí; no lee .env."""

import base64
import os

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
