"""Regla del semáforo (contexto.md 4.7)."""

from datetime import datetime, timedelta

import pytest

from radica.dominio.plazos import ZONA_COLOMBIA
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import Semaforo

RADICACION = datetime(2026, 10, 30, 16, tzinfo=ZONA_COLOMBIA)
VENCIMIENTO = RADICACION + timedelta(hours=48)


@pytest.fixture
def regla() -> ReglaSemaforo:
    return ReglaSemaforo(umbral_amarillo=0.5)


def test_verde_con_mas_de_la_mitad_del_plazo(regla: ReglaSemaforo) -> None:
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, RADICACION + timedelta(hours=1))
    assert (lectura.color, lectura.horas_restantes) == (Semaforo.VERDE, 47.0)


def test_amarillo_justo_en_el_umbral(regla: ReglaSemaforo) -> None:
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, RADICACION + timedelta(hours=24))
    assert (lectura.color, lectura.horas_restantes) == (Semaforo.AMARILLO, 24.0)


def test_verde_un_segundo_antes_del_umbral(regla: ReglaSemaforo) -> None:
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, RADICACION + timedelta(hours=24, seconds=-1))
    assert lectura.color is Semaforo.VERDE


def test_ejemplo_7_4_de_la_entrega_2(regla: ReglaSemaforo) -> None:
    # Reclamo priorizado radicado el 30-oct 16:00, vence el 1-nov 16:00; consulta el 31-oct 19:30.
    ahora = datetime(2026, 10, 31, 19, 30, tzinfo=ZONA_COLOMBIA)
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, ahora)
    assert (lectura.color, lectura.horas_restantes) == (Semaforo.AMARILLO, 20.5)


def test_rojo_en_el_momento_del_vencimiento(regla: ReglaSemaforo) -> None:
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, VENCIMIENTO)
    assert (lectura.color, lectura.horas_restantes) == (Semaforo.ROJO, 0.0)


def test_rojo_con_horas_negativas_si_ya_vencio(regla: ReglaSemaforo) -> None:
    lectura = regla.evaluar(RADICACION, VENCIMIENTO, VENCIMIENTO + timedelta(hours=3, minutes=20))
    assert (lectura.color, lectura.horas_restantes) == (Semaforo.ROJO, -3.3)


def test_el_umbral_es_configurable() -> None:
    ahora = RADICACION + timedelta(hours=12)  # queda el 75 %
    assert ReglaSemaforo(0.5).evaluar(RADICACION, VENCIMIENTO, ahora).color is Semaforo.VERDE
    assert ReglaSemaforo(0.8).evaluar(RADICACION, VENCIMIENTO, ahora).color is Semaforo.AMARILLO


@pytest.mark.parametrize("umbral", [0, 1, -0.1, 1.5])
def test_el_umbral_debe_estar_entre_0_y_1(umbral: float) -> None:
    with pytest.raises(ValueError, match="entre 0 y 1"):
        ReglaSemaforo(umbral)
