"""CifradorAesGcm: implementación del puerto Cifrador con la librería cryptography."""

import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BYTES_LLAVE = 32
BYTES_NONCE = 12


class CifradorAesGcm:
    """AES-256-GCM con nonce aleatorio de 12 bytes por mensaje y HMAC-SHA-256."""

    def __init__(self, llave_cifrado: bytes, llave_hmac: bytes) -> None:
        if len(llave_cifrado) != BYTES_LLAVE or len(llave_hmac) != BYTES_LLAVE:
            raise ValueError(f"Las llaves deben tener {BYTES_LLAVE} bytes.")
        if llave_cifrado == llave_hmac:
            raise ValueError("La llave de cifrado y la de HMAC deben ser distintas.")
        self._aes = AESGCM(llave_cifrado)
        self._llave_hmac = llave_hmac

    def cifrar(self, texto: str) -> bytes:
        nonce = os.urandom(BYTES_NONCE)
        return nonce + self._aes.encrypt(nonce, texto.encode("utf-8"), None)

    def descifrar(self, cifrado: bytes) -> str:
        nonce, contenido = cifrado[:BYTES_NONCE], cifrado[BYTES_NONCE:]
        return self._aes.decrypt(nonce, contenido, None).decode("utf-8")

    def huella(self, texto: str) -> str:
        return hmac.new(self._llave_hmac, texto.encode("utf-8"), hashlib.sha256).hexdigest()
