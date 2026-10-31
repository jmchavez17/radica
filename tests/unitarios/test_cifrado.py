"""CifradorAesGcm (contexto.md 4.2). Usa llaves generadas en la prueba, nunca las del .env."""

import hashlib
import hmac
import os

import pytest
from cryptography.exceptions import InvalidTag

from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm

LLAVE_CIFRADO = os.urandom(32)
LLAVE_HMAC = os.urandom(32)


@pytest.fixture
def cifrador() -> CifradorAesGcm:
    return CifradorAesGcm(LLAVE_CIFRADO, LLAVE_HMAC)


def test_cifra_y_descifra(cifrador: CifradorAesGcm) -> None:
    texto = "Usuario Sintético Uno"
    cifrado = cifrador.cifrar(texto)

    assert texto.encode() not in cifrado
    assert cifrador.descifrar(cifrado) == texto


def test_cada_cifrado_lleva_su_propio_nonce(cifrador: CifradorAesGcm) -> None:
    primero, segundo = cifrador.cifrar("mismo texto"), cifrador.cifrar("mismo texto")

    assert primero[:12] != segundo[:12]
    assert primero != segundo


def test_guarda_nonce_mas_texto_cifrado_con_etiqueta(cifrador: CifradorAesGcm) -> None:
    # 12 bytes de nonce + texto + 16 bytes de etiqueta de autenticación.
    assert len(cifrador.cifrar("abcd")) == 12 + 4 + 16


def test_un_dato_alterado_no_se_descifra(cifrador: CifradorAesGcm) -> None:
    cifrado = bytearray(cifrador.cifrar("texto"))
    cifrado[-1] ^= 1
    with pytest.raises(InvalidTag):
        cifrador.descifrar(bytes(cifrado))


def test_otra_llave_no_descifra(cifrador: CifradorAesGcm) -> None:
    otro = CifradorAesGcm(os.urandom(32), LLAVE_HMAC)
    with pytest.raises(InvalidTag):
        otro.descifrar(cifrador.cifrar("texto"))


def test_la_huella_es_hmac_sha256_en_hexadecimal(cifrador: CifradorAesGcm) -> None:
    huella = cifrador.huella("CC:1000000001")

    assert huella == hmac.new(LLAVE_HMAC, b"CC:1000000001", hashlib.sha256).hexdigest()
    assert len(huella) == 64
    assert huella == cifrador.huella("CC:1000000001")
    assert huella != cifrador.huella("TI:1000000001")


def test_la_huella_depende_de_la_llave(cifrador: CifradorAesGcm) -> None:
    otro = CifradorAesGcm(LLAVE_CIFRADO, os.urandom(32))
    assert otro.huella("CC:1000000001") != cifrador.huella("CC:1000000001")


@pytest.mark.parametrize(
    ("cifrado", "hmac_"),
    [(os.urandom(16), LLAVE_HMAC), (LLAVE_CIFRADO, os.urandom(31)), (LLAVE_CIFRADO, LLAVE_CIFRADO)],
    ids=["cifrado-corta", "hmac-corta", "llaves-iguales"],
)
def test_rechaza_llaves_invalidas(cifrado: bytes, hmac_: bytes) -> None:
    with pytest.raises(ValueError):
        CifradorAesGcm(cifrado, hmac_)
