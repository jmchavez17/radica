"""Datos compartidos por las pruebas unitarias.

Copian los términos y festivos semilla de docs/modelo-datos.md (2.2 y 2.3)
para probar las reglas sin base de datos.
"""

from datetime import date

import pytest

from radica.dominio.plazos import Termino
from radica.dominio.valores import NivelRiesgo, Poblacion, Regimen, TipoPqrs, Unidad

FESTIVOS_COLOMBIA = frozenset(
    {
        date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2),
        date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8),
        date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
        date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16),
        date(2026, 12, 8), date(2026, 12, 25),
        date(2027, 1, 1), date(2027, 1, 11), date(2027, 3, 22), date(2027, 3, 25),
        date(2027, 3, 26), date(2027, 5, 1), date(2027, 5, 10), date(2027, 5, 31),
        date(2027, 6, 7), date(2027, 7, 5), date(2027, 7, 20), date(2027, 8, 7),
        date(2027, 8, 16), date(2027, 10, 18), date(2027, 11, 1), date(2027, 11, 15),
        date(2027, 12, 8), date(2027, 12, 25),
    }
)

_INICIO = date(2026, 1, 1)
_LEY = "Ley 1755 de 2015, art. 14"
_CIRCULAR = "Supersalud, Circular Externa 2023151000000010-5"


def _general(id_termino: int, tipo: TipoPqrs, valor: int) -> Termino:
    return Termino(
        id_termino, Regimen.GENERAL, tipo, NivelRiesgo.NO_APLICA, Poblacion.TODAS, valor,
        Unidad.DIAS_HABILES, 1, _LEY, _INICIO,
    )


def _salud(id_termino: int, nivel: NivelRiesgo, poblacion: Poblacion, valor: int,
           fuente: str = _CIRCULAR, desde: date = _INICIO) -> Termino:
    return Termino(
        id_termino, Regimen.SALUD, TipoPqrs.RECLAMO, nivel, poblacion, valor,
        Unidad.HORAS_CORRIDAS, None, fuente, desde,
    )


TERMINOS_SEMILLA = (
    _general(1, TipoPqrs.PETICION, 15),
    _general(2, TipoPqrs.SOLICITUD_INFORMACION, 10),
    _general(3, TipoPqrs.CONSULTA, 30),
    _general(4, TipoPqrs.QUEJA, 15),
    _general(5, TipoPqrs.SUGERENCIA, 15),
    _salud(6, NivelRiesgo.SIMPLE, Poblacion.TODAS, 72),
    _salud(7, NivelRiesgo.PRIORIZADO, Poblacion.TODAS, 48),
    _salud(8, NivelRiesgo.VITAL, Poblacion.TODAS, 24),
    _salud(9, NivelRiesgo.VITAL, Poblacion.MENOR, 8,
           "Supersalud, Circular Externa 2026151000000007-5", date(2026, 6, 9)),
)


@pytest.fixture
def terminos() -> tuple[Termino, ...]:
    return TERMINOS_SEMILLA


@pytest.fixture
def festivos() -> frozenset[date]:
    return FESTIVOS_COLOMBIA
