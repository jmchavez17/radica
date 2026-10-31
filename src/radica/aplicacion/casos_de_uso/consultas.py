"""Casos de uso de lectura (contexto.md 4.10): consulta, bandeja, historial y términos.

El semáforo se calcula en el momento de la consulta con ReglaSemaforo; no se
guarda. La bandeja filtra por semáforo y pagina en memoria, porque el color
depende de la hora (decisión de la sesión 2, duda 4; unas 350 PQRS al mes).
"""

from collections.abc import Callable
from datetime import datetime

from radica.aplicacion.casos_de_uso.errores import PqrsNoEncontrada
from radica.aplicacion.casos_de_uso.resultados import PaginaBandeja, PqrsConSemaforo
from radica.aplicacion.puertos.auditoria import AuditoriaRepository
from radica.aplicacion.puertos.configuracion import ConfiguracionRepository
from radica.aplicacion.puertos.pqrs import FiltroBandeja, PqrsRepository, VistaPqrs
from radica.dominio.plazos import Termino, dia_en_colombia
from radica.dominio.pqrs import EventoAuditoria
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import Semaforo


def _con_semaforo(vista: VistaPqrs, regla: ReglaSemaforo, ahora: datetime) -> PqrsConSemaforo:
    return PqrsConSemaforo(vista, regla.evaluar(vista.fecha_radicacion, vista.fecha_vencimiento, ahora))


class ConsultarPqrs:
    def __init__(
        self, pqrs: PqrsRepository, semaforo: ReglaSemaforo, reloj: Callable[[], datetime]
    ) -> None:
        self._pqrs = pqrs
        self._semaforo = semaforo
        self._reloj = reloj

    def ejecutar(self, id_pqrs: int) -> PqrsConSemaforo:
        vista = self._pqrs.obtener(id_pqrs)
        if vista is None:
            raise PqrsNoEncontrada(id_pqrs)
        return _con_semaforo(vista, self._semaforo, self._reloj())


class ListarBandeja:
    """Ordena por vencimiento ascendente (las vencidas quedan primero) y luego por id."""

    def __init__(
        self, pqrs: PqrsRepository, semaforo: ReglaSemaforo, reloj: Callable[[], datetime]
    ) -> None:
        self._pqrs = pqrs
        self._semaforo = semaforo
        self._reloj = reloj

    def ejecutar(
        self, filtro: FiltroBandeja, semaforo: Semaforo | None, pagina: int, tamano: int
    ) -> PaginaBandeja:
        if pagina < 1 or tamano < 1:
            raise ValueError("pagina y tamano empiezan en 1.")
        ahora = self._reloj()
        elementos = [_con_semaforo(vista, self._semaforo, ahora) for vista in self._pqrs.listar(filtro)]
        if semaforo is not None:
            elementos = [elemento for elemento in elementos if elemento.semaforo.color is semaforo]
        inicio = (pagina - 1) * tamano
        return PaginaBandeja(pagina, len(elementos), elementos[inicio : inicio + tamano])


class ConsultarHistorial:
    def __init__(self, pqrs: PqrsRepository, auditoria: AuditoriaRepository) -> None:
        self._pqrs = pqrs
        self._auditoria = auditoria

    def ejecutar(self, id_pqrs: int) -> list[EventoAuditoria]:
        if not self._pqrs.existe(id_pqrs):
            raise PqrsNoEncontrada(id_pqrs)
        return self._auditoria.historial(id_pqrs)


class ListarTerminos:
    def __init__(self, configuracion: ConfiguracionRepository, reloj: Callable[[], datetime]) -> None:
        self._configuracion = configuracion
        self._reloj = reloj

    def ejecutar(self) -> tuple[Termino, ...]:
        """Términos vigentes hoy, en hora de Colombia."""
        return self._configuracion.terminos_vigentes(dia_en_colombia(self._reloj()))
