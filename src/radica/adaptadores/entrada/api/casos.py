"""Lo que la API necesita de la raíz de composición: los casos de uso de una solicitud."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from radica.aplicacion.casos_de_uso.consultas import (
    ConsultarHistorial,
    ConsultarPqrs,
    ListarBandeja,
    ListarTerminos,
)
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs
from radica.aplicacion.casos_de_uso.solicitar_clasificacion import SolicitarClasificacion


@dataclass(frozen=True)
class CasosDeUso:
    registrar: RegistrarPqrs
    consultar: ConsultarPqrs
    bandeja: ListarBandeja
    historial: ConsultarHistorial
    terminos: ListarTerminos
    solicitar_clasificacion: SolicitarClasificacion


# Abre una unidad de trabajo: confirma al salir sin error y deshace si hay una excepción.
FabricaDeCasos = Callable[[], AbstractContextManager[CasosDeUso]]
