"""ClasificadorConRespaldo (Entrega 2, 10.4): prueba una lista ordenada de clasificadores.

Es un decorador del mismo puerto ClasificadorPqrs; lo arma la raíz de
composición, por defecto con Claude y después las palabras clave. Si uno
lanza ProveedorNoDisponible o SalidaInvalida pasa al siguiente y acumula sus
intentos en intentos_fallidos, para que el caso de uso los guarde en
llamada_ia. Si fallan todos, lanza el error del último con todos los intentos.
"""

from collections.abc import Sequence
from dataclasses import replace

from radica.aplicacion.puertos.clasificador import (
    ClasificadorPqrs,
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    SolicitudClasificacion,
    UsoIA,
)


class ClasificadorConRespaldo:
    def __init__(self, clasificadores: Sequence[ClasificadorPqrs]) -> None:
        if not clasificadores:
            raise ValueError("ClasificadorConRespaldo necesita al menos un clasificador.")
        self._clasificadores = tuple(clasificadores)

    @property
    def clasificadores(self) -> tuple[ClasificadorPqrs, ...]:
        return self._clasificadores

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        fallidos: list[UsoIA] = []
        ultimo: ProveedorNoDisponible | SalidaInvalida | None = None
        for clasificador in self._clasificadores:
            try:
                resultado = clasificador.clasificar(solicitud)
            except (ProveedorNoDisponible, SalidaInvalida) as error:
                fallidos.extend(error.intentos)
                ultimo = error
                continue
            return replace(resultado, intentos_fallidos=(*fallidos, *resultado.intentos_fallidos))
        assert ultimo is not None
        raise type(ultimo)(str(ultimo), tuple(fallidos))
