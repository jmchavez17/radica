"""CalculadoraDePlazos y selección del término (contexto.md 4.6)."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from radica.dominio.plazos import (
    ZONA_COLOMBIA,
    CalculadoraDePlazos,
    Termino,
    TerminoNoConfigurado,
    nivel_efectivo,
    seleccionar_termino,
)
from radica.dominio.valores import NivelRiesgo, Poblacion, TipoPqrs

P = TipoPqrs
N = NivelRiesgo


def _bogota(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=ZONA_COLOMBIA)


# Los 13 casos obligatorios: tipo, nivel, menor, radicación, vencimiento (hora de Colombia).
CASOS = [
    (1, P.PETICION, N.NO_APLICA, False, "2026-10-30 16:00", "2026-11-24 23:59:59"),
    (2, P.SOLICITUD_INFORMACION, N.NO_APLICA, False, "2026-10-30 09:00", "2026-11-17 23:59:59"),
    (3, P.CONSULTA, N.NO_APLICA, False, "2026-10-30 09:00", "2026-12-16 23:59:59"),
    (4, P.PETICION, N.NO_APLICA, False, "2026-10-31 10:00", "2026-11-24 23:59:59"),
    (5, P.PETICION, N.NO_APLICA, False, "2026-11-02 10:00", "2026-11-24 23:59:59"),
    (6, P.PETICION, N.NO_APLICA, False, "2026-12-18 10:00", "2027-01-13 23:59:59"),
    (7, P.QUEJA, N.NO_APLICA, False, "2026-12-24 10:00", "2027-01-19 23:59:59"),
    (8, P.SOLICITUD_INFORMACION, N.NO_APLICA, False, "2026-04-01 10:00", "2026-04-17 23:59:59"),
    (9, P.RECLAMO, N.SIMPLE, False, "2026-10-30 16:00", "2026-11-02 16:00"),
    (10, P.RECLAMO, N.PRIORIZADO, False, "2026-10-30 16:00", "2026-11-01 16:00"),
    (11, P.RECLAMO, N.VITAL, False, "2026-10-30 16:00", "2026-10-31 16:00"),
    (12, P.RECLAMO, N.VITAL, True, "2026-10-30 16:00", "2026-10-31 00:00"),
    (13, P.RECLAMO, N.VITAL, False, "2026-10-30 16:00", "2026-10-31 16:00"),
]


@pytest.mark.parametrize(
    ("caso", "tipo", "nivel", "menor", "radicacion", "esperado"),
    CASOS,
    ids=[f"caso-{caso[0]}" for caso in CASOS],
)
def test_casos_obligatorios_del_vencimiento(
    terminos: tuple[Termino, ...],
    festivos: frozenset[date],
    caso: int,
    tipo: TipoPqrs,
    nivel: NivelRiesgo,
    menor: bool,
    radicacion: str,
    esperado: str,
) -> None:
    fecha = _bogota(radicacion)
    termino = seleccionar_termino(terminos, tipo, nivel, menor, fecha)

    vencimiento = CalculadoraDePlazos().calcular(termino, fecha, festivos)

    assert vencimiento == _bogota(esperado)
    assert vencimiento.utcoffset() == ZONA_COLOMBIA.utcoffset(vencimiento)


def test_el_dia_de_radicacion_se_toma_en_hora_de_colombia(
    terminos: tuple[Termino, ...], festivos: frozenset[date]
) -> None:
    # 2026-10-31T02:00Z es todavía el viernes 30 a las 21:00 en Colombia.
    fecha = datetime.fromisoformat("2026-10-31T02:00:00+00:00")
    termino = seleccionar_termino(terminos, P.PETICION, N.NO_APLICA, False, fecha)

    assert CalculadoraDePlazos().calcular(termino, fecha, festivos) == _bogota("2026-11-24 23:59:59")


def test_las_horas_corridas_no_dependen_de_la_zona_de_entrada(terminos: tuple[Termino, ...]) -> None:
    fecha = datetime.fromisoformat("2026-10-30T21:00:00+00:00")  # 16:00 en Colombia
    termino = seleccionar_termino(terminos, P.RECLAMO, N.SIMPLE, False, fecha)

    assert CalculadoraDePlazos().calcular(termino, fecha, frozenset()) == _bogota("2026-11-02 16:00")


def test_la_calculadora_rechaza_fechas_sin_zona(terminos: tuple[Termino, ...]) -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        CalculadoraDePlazos().calcular(terminos[0], datetime(2026, 10, 30, 16), frozenset())


def test_un_reclamo_sin_nivel_queda_simple(terminos: tuple[Termino, ...]) -> None:
    assert nivel_efectivo(P.RECLAMO, N.NO_APLICA) is N.SIMPLE
    termino = seleccionar_termino(terminos, P.RECLAMO, N.NO_APLICA, False, _bogota("2026-10-30 16:00"))
    assert termino.id == 6


@pytest.mark.parametrize("nivel", list(NivelRiesgo))
def test_los_demas_tipos_ignoran_el_nivel_de_riesgo(
    terminos: tuple[Termino, ...], nivel: NivelRiesgo
) -> None:
    assert nivel_efectivo(P.QUEJA, nivel) is nivel
    termino = seleccionar_termino(terminos, P.QUEJA, nivel, True, _bogota("2026-10-30 16:00"))
    assert termino.id == 4


@pytest.mark.parametrize("nivel", [N.SIMPLE, N.PRIORIZADO])
def test_menor_de_edad_solo_cambia_el_termino_con_riesgo_vital(
    terminos: tuple[Termino, ...], nivel: NivelRiesgo
) -> None:
    termino = seleccionar_termino(terminos, P.RECLAMO, nivel, True, _bogota("2026-10-30 16:00"))
    assert termino.poblacion is Poblacion.TODAS


def test_menor_vital_antes_de_la_circular_usa_el_termino_de_todas(
    terminos: tuple[Termino, ...],
) -> None:
    termino = seleccionar_termino(terminos, P.RECLAMO, N.VITAL, True, _bogota("2026-06-08 23:00"))
    assert (termino.id, termino.valor) == (8, 24)

    termino = seleccionar_termino(terminos, P.RECLAMO, N.VITAL, True, _bogota("2026-06-09 00:00"))
    assert (termino.id, termino.valor) == (9, 8)


def test_sin_termino_vigente_es_un_error_de_configuracion(terminos: tuple[Termino, ...]) -> None:
    with pytest.raises(TerminoNoConfigurado, match="PETICION"):
        seleccionar_termino(terminos, P.PETICION, N.NO_APLICA, False, _bogota("2025-12-31 10:00"))


def test_dos_terminos_vigentes_tambien_es_un_error(terminos: tuple[Termino, ...]) -> None:
    with pytest.raises(TerminoNoConfigurado, match="2 términos"):
        seleccionar_termino(
            (*terminos, terminos[0]), P.PETICION, N.NO_APLICA, False, _bogota("2026-10-30 10:00")
        )


def test_un_termino_vencido_no_se_selecciona(terminos: tuple[Termino, ...]) -> None:
    vencido = replace(terminos[0], vigente_hasta=date(2026, 10, 29))
    with pytest.raises(TerminoNoConfigurado):
        seleccionar_termino((vencido,), P.PETICION, N.NO_APLICA, False, _bogota("2026-10-30 10:00"))


def test_textos_de_regla(terminos: tuple[Termino, ...]) -> None:
    assert [termino.regla for termino in terminos] == [
        "Petición: 15 días hábiles",
        "Solicitud de información: 10 días hábiles",
        "Consulta: 30 días hábiles",
        "Queja: 15 días hábiles",
        "Sugerencia: 15 días hábiles",
        "Reclamo en salud, riesgo simple: 72 horas corridas",
        "Reclamo en salud, riesgo priorizado: 48 horas corridas",
        "Reclamo en salud, riesgo vital: 24 horas corridas",
        "Reclamo en salud, riesgo vital, paciente menor de edad: 8 horas",
    ]
