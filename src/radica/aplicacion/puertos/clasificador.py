"""Puerto ClasificadorPqrs y su contrato (Entrega 2, secciones 5.3, 9.3 y 10.1).

Lo implementarán AdaptadorClaude, ClasificadorPalabrasClave y
ClasificadorConRespaldo. Frente al código de la sección 10.1, el equipo aprobó
el 31-oct-2026: uso y resumen opcionales, senales_riesgo, datos_clave
inmutable y la validación de la confianza (docs/uso-de-ia.md, sesión 1).
Cambiar este contrato exige acordarlo con quien implementa cada clasificador.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol

from radica.dominio.valores import NivelRiesgo, TipoPqrs


@dataclass(frozen=True)
class AtributoCatalogo:
    """Atributo de calidad vigente, tal como se le ofrece al clasificador."""

    id: int
    nombre: str
    definicion: str


@dataclass(frozen=True)
class AreaCatalogo:
    """Área responsable vigente, tal como se le ofrece al clasificador."""

    id: int
    nombre: str


@dataclass(frozen=True)
class Catalogo:
    """Valores entre los que el clasificador puede elegir."""

    tipos: tuple[TipoPqrs, ...]
    atributos: tuple[AtributoCatalogo, ...]
    areas: tuple[AreaCatalogo, ...]


@dataclass(frozen=True)
class UsoIA:
    """Consumo de una llamada a un proveedor externo; corresponde a una fila de llamada_ia."""

    proveedor: str
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    costo_usd: Decimal
    latencia_ms: int


@dataclass(frozen=True)
class SolicitudClasificacion:
    """Lo que recibe un clasificador.

    texto_enmascarado ya pasó el enmascaramiento verificado (ADR-03).
    id_pqrs es interno: sirve para trazar, nunca se envía al proveedor.
    """

    id_pqrs: int
    texto_enmascarado: str
    catalogo: Catalogo
    version_instrucciones: str


@dataclass(frozen=True)
class ResultadoClasificacion:
    """Sugerencia de un clasificador, con valores del dominio en español.

    id_atributo e id_area son ids del catálogo de la solicitud, o None.
    confianza va entre 0 y 1 (las reglas usan 0,5 fijo).
    senales_riesgo: frases que justifican el nivel de riesgo; en el
    clasificador por reglas, las palabras de alarma encontradas.
    uso: consumo del proveedor externo; None cuando respondió un clasificador
    local sin proveedor (palabras clave).
    """

    tipo: TipoPqrs
    id_atributo: int | None
    id_area: int | None
    nivel_riesgo: NivelRiesgo
    confianza: float
    resumen: str | None = None
    datos_clave: Mapping[str, str] = field(default_factory=dict)
    senales_riesgo: tuple[str, ...] = ()
    uso: UsoIA | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confianza <= 1:
            raise ValueError(f"La confianza debe estar entre 0 y 1; se recibió {self.confianza}.")
        object.__setattr__(self, "datos_clave", MappingProxyType(dict(self.datos_clave)))


class ProveedorNoDisponible(Exception):
    """El proveedor no respondió a tiempo, rechazó la solicitud o falló."""


class SalidaInvalida(Exception):
    """La respuesta no cumple el esquema o trae valores fuera del catálogo."""


class ClasificadorPqrs(Protocol):
    """Puerto de clasificación de una PQRS.

    Garantías de toda implementación (sección 10.1): devuelve valores del
    dominio en español, nunca etiquetas propias del proveedor; confianza entre
    0 y 1; solo lanza ProveedorNoDisponible o SalidaInvalida; no guarda nada
    por su cuenta; responde en máximo 15 s por intento.
    """

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        """Clasifica el texto enmascarado. Solo lanza ProveedorNoDisponible o SalidaInvalida."""
        ...
