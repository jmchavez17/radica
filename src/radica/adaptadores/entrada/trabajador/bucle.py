"""Trabajador: clasifica con IA en segundo plano (contexto.md 4.9, ADR-04).

Es otro punto de entrada del mismo código y otro servicio de Docker Compose.
Cada vuelta abre una unidad de trabajo (una transacción): toma la PQRS
PENDIENTE más antigua con SELECT … FOR UPDATE SKIP LOCKED y la clasifica
mientras la tiene bloqueada. Si no hay pendientes, espera unos segundos.
No conoce la base de datos ni los adaptadores de salida: la unidad de trabajo
se la entrega main.py.

Si la clasificación falla por un error inesperado, la transacción se deshace
y, en otra, la PQRS queda FALLIDA para no tomarla otra vez (decisión D2). Los
intentos de llamada_ia de esa transacción se pierden con ella.
"""

import logging
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager

from radica.aplicacion.casos_de_uso.clasificar_pqrs import ClasificarPqrs

registro = logging.getLogger("radica.trabajador")

INTERVALO_S = 5.0  # contexto.md §5 no define una variable para esto

# Abre una unidad de trabajo: confirma al salir sin error y deshace si hay una excepción.
FabricaDeClasificacion = Callable[[], AbstractContextManager[ClasificarPqrs]]


class Trabajador:
    def __init__(self, unidad_de_trabajo: FabricaDeClasificacion, intervalo_s: float = INTERVALO_S) -> None:
        self._unidad = unidad_de_trabajo
        self._intervalo = intervalo_s
        self._detenido = threading.Event()

    def procesar_una(self) -> bool:
        """Clasifica una PQRS pendiente; False si no había ninguna."""
        id_pqrs: int | None = None
        try:
            with self._unidad() as caso:
                id_pqrs = caso.tomar_siguiente()
                if id_pqrs is None:
                    return False
                estado_ia = caso.ejecutar(id_pqrs)
            registro.info("PQRS %d clasificada: estado_ia=%s", id_pqrs, estado_ia.value)
            return True
        except Exception as error:
            if id_pqrs is None:
                raise
            # Solo el tipo del error: el mensaje o la traza podrían traer parte del texto.
            registro.error("Error inesperado (%s) al clasificar la PQRS %d", type(error).__name__, id_pqrs)
            with self._unidad() as caso:
                caso.registrar_error_interno(id_pqrs)
            return True

    def ejecutar(self) -> None:
        """Repite hasta detener(); un fallo de la base no lo tumba, espera y reintenta."""
        registro.info("Trabajador iniciado; revisa las pendientes cada %.0f s", self._intervalo)
        while not self._detenido.is_set():
            try:
                hubo = self.procesar_una()
            except Exception as error:
                registro.error("No se pudo procesar la cola de clasificación (%s)", type(error).__name__)
                hubo = False
            if not hubo:
                self._detenido.wait(self._intervalo)
        registro.info("Trabajador detenido")

    def detener(self) -> None:
        self._detenido.set()
