"""Resultados compartidos por los casos de uso de registro y consulta."""

from dataclasses import dataclass

from radica.aplicacion.puertos.pqrs import VistaPqrs
from radica.dominio.semaforo import LecturaSemaforo


@dataclass(frozen=True)
class PqrsConSemaforo:
    """Una PQRS con el semáforo calculado en el momento de la consulta."""

    pqrs: VistaPqrs
    semaforo: LecturaSemaforo


@dataclass(frozen=True)
class PaginaBandeja:
    pagina: int
    total: int
    elementos: list[PqrsConSemaforo]
