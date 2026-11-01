"""Errores de los casos de uso que la API traduce a Problem Details (contexto.md 4.11)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDeCampo:
    campo: str  # nombre del dato en el caso de uso, en snake_case
    mensaje: str  # en español y sin repetir el valor recibido


class DatosInvalidos(Exception):
    """Validación de negocio que no puede hacer el esquema de entrada (400)."""

    def __init__(self, errores: list[ErrorDeCampo]) -> None:
        super().__init__(f"{len(errores)} errores de validación")
        self.errores = errores


class PqrsNoEncontrada(Exception):
    """No existe una PQRS con ese id (404)."""

    def __init__(self, id_pqrs: int) -> None:
        super().__init__(f"No existe la PQRS {id_pqrs}")
        self.id_pqrs = id_pqrs


class OperacionNoPermitida(Exception):
    """El estado actual de la PQRS no permite la operación (409). detalle va en español para la API."""

    def __init__(self, detalle: str) -> None:
        super().__init__(detalle)
        self.detalle = detalle
