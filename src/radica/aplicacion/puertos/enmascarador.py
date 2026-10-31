"""Puerto Enmascarador (contexto.md 4.4, ADR-03, HU-03).

Recibe también los datos del peticionario para reemplazar sus apariciones
exactas además de lo que detectan las reglas. Ningún resultado lleva los
valores encontrados: solo marcadores y tipos.
"""

from dataclasses import dataclass
from typing import Protocol

from radica.dominio.peticionario import DatosPeticionario

TIPOS_DE_DATO = ("CEDULA", "TELEFONO", "CORREO", "HC", "NOMBRE")


@dataclass(frozen=True)
class TextoEnmascarado:
    texto: str
    marcadores: tuple[str, ...]  # en orden de aparición, sin repetir: ("TELEFONO_1", "CORREO_1")


@dataclass(frozen=True)
class Verificacion:
    """Resultado de volver a pasar los detectores sobre un texto enmascarado."""

    limpio: bool
    tipos_detectados: tuple[str, ...] = ()  # por ejemplo ("TELEFONO",); nunca los valores


class Enmascarador(Protocol):
    def enmascarar(self, texto: str, datos: DatosPeticionario) -> TextoEnmascarado:
        """Reemplaza cada dato por [TIPO_n]; el mismo valor recibe el mismo marcador."""
        ...

    def verificar(self, texto_enmascarado: str, datos: DatosPeticionario) -> Verificacion:
        """Comprueba que no queda ningún dato detectable ni ningún valor del peticionario."""
        ...
