"""Contrato del puerto ClasificadorPqrs: lo que toda implementación puede suponer."""

from dataclasses import FrozenInstanceError

import pytest

from radica.aplicacion.puertos.clasificador import (
    AreaCatalogo,
    Catalogo,
    ClasificadorPqrs,
    ResultadoClasificacion,
    SolicitudClasificacion,
)
from radica.dominio.valores import NivelRiesgo, TipoPqrs


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
