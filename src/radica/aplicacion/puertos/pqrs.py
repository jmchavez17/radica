"""Puerto PqrsRepository (Entrega 2, 5.3) y las vistas de lectura que devuelve.

Frente a la sección 5.3 agrega reservar_id (nextval, para armar el radicado
antes de insertar), obtener_o_crear_peticionario, guardar_clasificacion y
existe. pendientes_de_ia queda para la sesión del trabajador.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from radica.dominio.plazos import Termino
from radica.dominio.pqrs import Clasificacion, PeticionarioCifrado, Pqrs, Referencia
from radica.dominio.valores import (
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    TipoPqrs,
)


@dataclass(frozen=True)
class ClasificacionVigente:
    """Clasificación vigente con los nombres del catálogo; modelo y versión solo si es de IA."""

    origen: OrigenClasificacion
    tipo: TipoPqrs
    atributo: Referencia | None
    area: Referencia | None
    nivel_riesgo: NivelRiesgo
    confianza: float
    resumen: str | None = None
    modelo: str | None = None
    version_instrucciones: str | None = None


@dataclass(frozen=True)
class VistaPqrs:
    """Lo que muestran la consulta y la bandeja. Nunca lleva datos del peticionario."""

    id: int
    radicado: str
    canal: Canal
    sede: str | None
    fecha_radicacion: datetime
    texto_enmascarado: str
    tipo: TipoPqrs
    nivel_riesgo: NivelRiesgo
    estado: EstadoPqrs
    estado_ia: EstadoIa
    fecha_vencimiento: datetime
    termino: Termino
    clasificacion: ClasificacionVigente | None
    responsable: Referencia | None = None


@dataclass(frozen=True)
class FiltroBandeja:
    """Filtros que resuelve el repositorio; el semáforo se filtra al consultar porque no se guarda."""

    estado: EstadoPqrs | None = None
    tipo: TipoPqrs | None = None
    id_area: int | None = None  # área sugerida de la clasificación vigente


class PqrsRepository(Protocol):
    def reservar_id(self) -> int:
        """Siguiente id de pqrs (nextval). Si el registro falla, el número se pierde."""
        ...

    def obtener_o_crear_peticionario(self, peticionario: PeticionarioCifrado) -> int:
        """Id del peticionario con ese documento_hash; si ya existe, no sobrescribe sus datos."""
        ...

    def guardar(self, pqrs: Pqrs) -> None: ...

    def guardar_clasificacion(self, id_pqrs: int, clasificacion: Clasificacion) -> int: ...

    def obtener(self, id_pqrs: int) -> VistaPqrs | None: ...

    def listar(self, filtro: FiltroBandeja) -> list[VistaPqrs]:
        """Todas las que cumplen el filtro, por fecha de vencimiento ascendente y luego por id."""
        ...

    def existe(self, id_pqrs: int) -> bool: ...
