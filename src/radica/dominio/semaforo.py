"""Regla del semáforo (contexto.md 4.7, HU-08).

SUPUESTO (validar en V3): fracción restante = (vencimiento − ahora) /
(vencimiento − radicación). Se calcula al consultar; no se guarda.
"""

from dataclasses import dataclass
from datetime import datetime

from radica.dominio.valores import Semaforo


@dataclass(frozen=True)
class LecturaSemaforo:
    color: Semaforo
    horas_restantes: float  # un decimal; negativo si ya venció


class ReglaSemaforo:
    """ROJO si ya venció; AMARILLO si queda una fracción ≤ umbral; VERDE en otro caso."""

    def __init__(self, umbral_amarillo: float) -> None:
        if not 0 < umbral_amarillo < 1:
            raise ValueError("El umbral amarillo debe estar entre 0 y 1.")
        self._umbral = umbral_amarillo

    def evaluar(self, radicacion: datetime, vencimiento: datetime, ahora: datetime) -> LecturaSemaforo:
        restante = vencimiento - ahora
        total = vencimiento - radicacion
        horas = round(restante.total_seconds() / 3600, 1)
        if restante.total_seconds() <= 0:
            return LecturaSemaforo(Semaforo.ROJO, horas)
        fraccion = restante / total if total.total_seconds() > 0 else 0.0
        color = Semaforo.AMARILLO if fraccion <= self._umbral else Semaforo.VERDE
        return LecturaSemaforo(color, horas)
