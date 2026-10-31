"""Puerto Cifrador: protección de los datos del peticionario (contexto.md 4.2, Entrega 2 6.3).

No está en la lista de puertos de la sección 5.3; se agregó en la sesión 2
para que RegistrarPqrs cifre sin conocer la librería de criptografía.
"""

from typing import Protocol


class Cifrador(Protocol):
    def cifrar(self, texto: str) -> bytes:
        """Cifra con AES-256-GCM; devuelve nonce + texto cifrado."""
        ...

    def descifrar(self, cifrado: bytes) -> str:
        """Inverso de cifrar(). Falla si el dato fue alterado o la llave es otra."""
        ...

    def huella(self, texto: str) -> str:
        """HMAC-SHA-256 en hexadecimal (64 caracteres), con una llave distinta a la de cifrado."""
        ...
