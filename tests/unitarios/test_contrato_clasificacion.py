"""Contrato del puerto ClasificadorPqrs: lo que toda implementación puede suponer."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from radica.aplicacion.puertos.clasificador import (
    AreaCatalogo,
    Catalogo,
    ClasificadorPqrs,
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    SolicitudClasificacion,
    UsoIA,
)
from radica.dominio.valores import NivelRiesgo, ResultadoLlamadaIA, TipoPqrs


def _resultado(**cambios: object) -> ResultadoClasificacion:
    campos: dict[str, object] = {
        "tipo": TipoPqrs.RECLAMO,
        "id_atributo": 2,
        "id_area": 4,
        "nivel_riesgo": NivelRiesgo.SIMPLE,
        "confianza": 0.5,
    }
    return ResultadoClasificacion(**(campos | cambios))  # type: ignore[arg-type]


def test_los_campos_opcionales_tienen_valores_por_defecto() -> None:
    resultado = _resultado()
    assert resultado.resumen is None
    assert dict(resultado.datos_clave) == {}
    assert resultado.senales_riesgo == ()
    assert resultado.uso is None
    assert resultado.intentos_fallidos == ()


# Extensión de la sesión 4 (acordada con Isabella): cada intento es una fila de llamada_ia.

def _uso(**cambios: object) -> UsoIA:
    campos: dict[str, object] = {
        "proveedor": "anthropic",
        "modelo": "claude-haiku-5-5",
        "tokens_entrada": 0,
        "tokens_salida": 0,
        "costo_usd": Decimal(0),
        "latencia_ms": 15000,
    }
    return UsoIA(**(campos | cambios))  # type: ignore[arg-type]


def test_un_uso_sin_intento_ni_resultado_es_el_primer_intento_ok() -> None:
    uso = _uso()
    assert uso.intento == 1
    assert uso.resultado is ResultadoLlamadaIA.OK


def test_el_resultado_lleva_los_intentos_fallidos_en_orden() -> None:
    fallidos = (
        _uso(intento=1, resultado=ResultadoLlamadaIA.TIMEOUT),
        _uso(intento=2, resultado=ResultadoLlamadaIA.LIMITE_CUOTA),
    )
    resultado = _resultado(uso=_uso(intento=3), intentos_fallidos=fallidos)
    assert [uso.intento for uso in resultado.intentos_fallidos] == [1, 2]
    assert resultado.uso is not None and resultado.uso.intento == 3


@pytest.mark.parametrize("error", [ProveedorNoDisponible, SalidaInvalida])
def test_los_errores_del_puerto_pueden_llevar_sus_intentos(error: type[Exception]) -> None:
    intentos = (_uso(resultado=ResultadoLlamadaIA.SALIDA_INVALIDA),)
    with pytest.raises(error) as capturado:
        raise error("sin respuesta válida", intentos)  # type: ignore[call-arg]
    assert capturado.value.intentos == intentos  # type: ignore[attr-defined]
    assert str(capturado.value) == "sin respuesta válida"


@pytest.mark.parametrize("error", [ProveedorNoDisponible, SalidaInvalida])
def test_sin_intentos_los_errores_siguen_funcionando_como_antes(error: type[Exception]) -> None:
    assert error().intentos == ()  # type: ignore[attr-defined]


@pytest.mark.parametrize("confianza", [0, 0.75, 1])
def test_acepta_confianza_entre_0_y_1(confianza: float) -> None:
    assert _resultado(confianza=confianza).confianza == confianza


@pytest.mark.parametrize("confianza", [-0.01, 1.01, float("nan")])
def test_rechaza_confianza_fuera_de_rango(confianza: float) -> None:
    with pytest.raises(ValueError, match="entre 0 y 1"):
        _resultado(confianza=confianza)


def test_el_resultado_es_inmutable() -> None:
    datos = {"servicio": "resonancia"}
    resultado = _resultado(datos_clave=datos)
    datos["servicio"] = "otro"
    assert resultado.datos_clave["servicio"] == "resonancia"
    with pytest.raises(TypeError):
        resultado.datos_clave["nuevo"] = "valor"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        resultado.tipo = TipoPqrs.QUEJA  # type: ignore[misc]


def test_una_clase_con_clasificar_cumple_el_puerto() -> None:
    class ClasificadorFijo:
        def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
            return _resultado(id_area=solicitud.catalogo.areas[0].id)

    clasificador: ClasificadorPqrs = ClasificadorFijo()
    solicitud = SolicitudClasificacion(
        id_pqrs=1,
        texto_enmascarado="No me han dado la autorización. Mi teléfono es [TELEFONO_1].",
        catalogo=Catalogo(
            tipos=tuple(TipoPqrs), atributos=(), areas=(AreaCatalogo(4, "Autorizaciones"),)
        ),
        version_instrucciones="clasif-v1.0",
    )
    assert clasificador.clasificar(solicitud).id_area == 4
