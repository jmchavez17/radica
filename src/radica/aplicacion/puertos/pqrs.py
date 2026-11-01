"""Puerto PqrsRepository (Entrega 2, 5.3) y las vistas de lectura que devuelve.

Frente a la sección 5.3 agrega reservar_id (nextval, para armar el radicado
antes de insertar), obtener_o_crear_peticionario, guardar_clasificacion y
existe. La sesión 4 agrega lo que necesitan ClasificarPqrs y el reintento:
pendientes_de_ia, obtener_para_clasificar, retirar_clasificacion_vigente,
actualizar_clasificacion, actualizar_estado y marcar_pendiente.
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


@dataclass(frozen=True)
class PqrsParaClasificar:
    """Lo que ClasificarPqrs necesita de una PQRS: su plazo vigente y los datos para verificar.

    tipo, id_atributo y nivel_riesgo son los de pqrs; id_area es el área
    sugerida de la clasificación vigente (pqrs.id_area sigue nulo, PB-13).
    """

    id: int
    fecha_radicacion: datetime
    texto_enmascarado: str
    paciente_menor: bool
    tipo: TipoPqrs
    id_atributo: int | None
    id_area: int | None
    nivel_riesgo: NivelRiesgo
    fecha_vencimiento: datetime
    estado: EstadoPqrs
    estado_ia: EstadoIa
    peticionario: PeticionarioCifrado


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

    def pendientes_de_ia(self, limite: int = 1) -> list[int]:
        """Ids de las PQRS con estado_ia PENDIENTE, de la más antigua a la más nueva.

        Las deja bloqueadas hasta el fin de la transacción y salta las que otro
        trabajador ya tomó (SELECT … FOR UPDATE SKIP LOCKED).
        """
        ...

    def obtener_para_clasificar(self, id_pqrs: int) -> PqrsParaClasificar | None: ...

    def retirar_clasificacion_vigente(self, id_pqrs: int) -> None:
        """La clasificación vigente pasa a vigente = false (solo puede haber una vigente)."""
        ...

    def actualizar_clasificacion(
        self,
        id_pqrs: int,
        tipo: TipoPqrs,
        id_atributo: int | None,
        nivel_riesgo: NivelRiesgo,
        id_termino: int,
        fecha_vencimiento: datetime,
    ) -> None: ...

    def actualizar_estado(self, id_pqrs: int, estado: EstadoPqrs, estado_ia: EstadoIa) -> None: ...

    def marcar_pendiente(self, id_pqrs: int, estado_ia_actual: EstadoIa) -> bool:
        """Pone estado_ia = PENDIENTE solo si sigue en estado_ia_actual; False si otro lo cambió antes."""
        ...
