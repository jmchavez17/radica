"""PoliticaDeRiesgo (contexto.md 4.9; RNF-07). Los plazos salen de la CalculadoraDePlazos real."""

from datetime import date, datetime, timedelta

import pytest

from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos, Termino, seleccionar_termino
from radica.dominio.riesgo import ClasificacionConPlazo, PoliticaDeRiesgo
from radica.dominio.valores import EstadoPqrs, NivelRiesgo, TipoPqrs

RADICACION = datetime(2026, 10, 30, 16, 0, tzinfo=ZONA_COLOMBIA)  # viernes


@pytest.fixture
def plazo(terminos: tuple[Termino, ...], festivos: frozenset[date]):
    calculadora = CalculadoraDePlazos()

    def calcular(tipo: TipoPqrs, nivel: NivelRiesgo, menor: bool = False) -> ClasificacionConPlazo:
        termino = seleccionar_termino(terminos, tipo, nivel, menor, RADICACION)
        dias = festivos if termino.id_calendario is not None else frozenset()
        return ClasificacionConPlazo(tipo, nivel, calculadora.calcular(termino, RADICACION, dias))

    return calcular


@pytest.fixture
def politica() -> PoliticaDeRiesgo:
    return PoliticaDeRiesgo(umbral_confianza=0.75)


# --- Casos de prueba de 4.9 que decide la política ---

def test_la_ia_sube_simple_a_priorizado_y_el_plazo_pasa_de_72_a_48_horas(plazo, politica) -> None:
    vigente = plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE)
    sugerida = plazo(TipoPqrs.RECLAMO, NivelRiesgo.PRIORIZADO)
    assert vigente.fecha_vencimiento - RADICACION == timedelta(hours=72)
    assert sugerida.fecha_vencimiento - RADICACION == timedelta(hours=48)

    decision = politica.decidir(vigente, sugerida, confianza=0.9)

    assert decision.aplicar
    assert decision.estado is EstadoPqrs.CLASIFICADA
    assert decision.motivo is None


def test_la_ia_baja_vital_a_simple_no_cambia_nada_y_pide_revision(plazo, politica) -> None:
    decision = politica.decidir(
        plazo(TipoPqrs.RECLAMO, NivelRiesgo.VITAL), plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), 0.95
    )

    assert not decision.aplicar
    assert decision.estado is EstadoPqrs.REQUIERE_REVISION
    assert decision.motivo == "La sugerencia de la IA alargaría el plazo vigente."


def test_la_ia_cambia_peticion_por_solicitud_de_informacion_y_queda_vigente(plazo, politica) -> None:
    vigente = plazo(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA)  # 15 días hábiles
    sugerida = plazo(TipoPqrs.SOLICITUD_INFORMACION, NivelRiesgo.NO_APLICA)  # 10 días hábiles
    assert sugerida.fecha_vencimiento < vigente.fecha_vencimiento

    decision = politica.decidir(vigente, sugerida, 0.9)

    assert decision.aplicar
    assert decision.estado is EstadoPqrs.CLASIFICADA


def test_confianza_0_6_queda_vigente_pero_requiere_revision(plazo, politica) -> None:
    vigente = plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE)

    decision = politica.decidir(vigente, plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), confianza=0.6)

    assert decision.aplicar
    assert decision.estado is EstadoPqrs.REQUIERE_REVISION
    assert decision.motivo == "Confianza 0,60 menor al umbral 0,75."


# --- Bordes ---

def test_el_mismo_vencimiento_se_aplica(plazo, politica) -> None:
    decision = politica.decidir(
        plazo(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA), plazo(TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA), 0.8
    )
    assert decision.aplicar


def test_la_confianza_igual_al_umbral_no_pide_revision(plazo, politica) -> None:
    vigente = plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE)
    assert politica.decidir(vigente, vigente, confianza=0.75).estado is EstadoPqrs.CLASIFICADA


def test_un_reclamo_que_la_ia_vuelve_peticion_alargaria_el_plazo(plazo, politica) -> None:
    decision = politica.decidir(
        plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), plazo(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA), 0.99
    )
    assert not decision.aplicar
    assert decision.requiere_revision


@pytest.mark.parametrize("nivel", [NivelRiesgo.PRIORIZADO, NivelRiesgo.VITAL])
def test_riesgo_alto_en_un_tipo_distinto_de_reclamo_queda_vigente_y_pide_revision(
    plazo, politica, nivel: NivelRiesgo
) -> None:
    decision = politica.decidir(
        plazo(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA), plazo(TipoPqrs.PETICION, nivel), 0.9
    )

    assert decision.aplicar
    assert decision.estado is EstadoPqrs.REQUIERE_REVISION
    assert decision.motivo == f"La IA marcó riesgo {nivel.value} en un tipo distinto de RECLAMO."


def test_baja_confianza_y_riesgo_alto_fuera_de_reclamo_dan_los_dos_motivos(plazo, politica) -> None:
    decision = politica.decidir(
        plazo(TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA), plazo(TipoPqrs.QUEJA, NivelRiesgo.VITAL), 0.5
    )
    assert decision.motivo == (
        "Confianza 0,50 menor al umbral 0,75. La IA marcó riesgo VITAL en un tipo distinto de RECLAMO."
    )


def test_con_el_mismo_plazo_no_se_aplica_una_sugerencia_que_baja_el_nivel(plazo, politica) -> None:
    # D7: una PETICION que una IA anterior dejó en VITAL conserva su nivel en un reintento.
    vigente = plazo(TipoPqrs.PETICION, NivelRiesgo.VITAL)
    sugerida = plazo(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA)
    assert sugerida.fecha_vencimiento == vigente.fecha_vencimiento

    decision = politica.decidir(vigente, sugerida, 0.99)

    assert not decision.aplicar
    assert decision.motivo == "La sugerencia de la IA bajaría el nivel de riesgo vigente."


def test_un_reclamo_con_no_aplica_cuenta_como_simple(plazo, politica) -> None:
    # nivel_efectivo: un RECLAMO nunca queda con NO_APLICA (4.6).
    vigente = plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE)
    assert politica.decidir(vigente, plazo(TipoPqrs.RECLAMO, NivelRiesgo.NO_APLICA), 0.9).aplicar


def test_vital_de_un_menor_acorta_a_8_horas(plazo, politica) -> None:
    vigente = plazo(TipoPqrs.RECLAMO, NivelRiesgo.VITAL, menor=True)
    sugerida = plazo(TipoPqrs.RECLAMO, NivelRiesgo.VITAL, menor=True)
    assert sugerida.fecha_vencimiento - RADICACION == timedelta(hours=8)
    assert politica.decidir(plazo(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), sugerida, 0.9).aplicar
    assert politica.decidir(vigente, sugerida, 0.9).aplicar


@pytest.mark.parametrize("umbral", [0, 1, -0.1])
def test_el_umbral_debe_estar_entre_0_y_1(umbral: float) -> None:
    with pytest.raises(ValueError, match="entre 0 y 1"):
        PoliticaDeRiesgo(umbral)
