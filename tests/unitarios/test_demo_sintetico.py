"""datos/sinteticos/demo.json: entradas válidas de POST /api/v1/pqrs, claramente sintéticas."""

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from radica.adaptadores.entrada.api.esquemas import PqrsNueva
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.adaptadores.salida.palabras_clave.clasificador import ClasificadorPalabrasClave
from radica.aplicacion.puertos.clasificador import AreaCatalogo, Catalogo, SolicitudClasificacion
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import (
    ZONA_COLOMBIA,
    CalculadoraDePlazos,
    Termino,
    nivel_efectivo,
    seleccionar_termino,
)
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import NivelRiesgo, Semaforo, TipoPqrs

RUTA = Path(__file__).resolve().parents[2] / "datos" / "sinteticos" / "demo.json"
CATALOGO = Catalogo(
    tipos=tuple(TipoPqrs), atributos=(), areas=tuple(AreaCatalogo(i, f"Área {i}") for i in range(1, 8))
)
AVANCES = datetime(2026, 11, 2, 8, tzinfo=ZONA_COLOMBIA)
ENTREGA = datetime(2026, 11, 4, 8, tzinfo=ZONA_COLOMBIA)

# Tipo, nivel y área esperados, en el orden del archivo.
ESPERADOS = [
    (TipoPqrs.RECLAMO, NivelRiesgo.VITAL, 7),
    (TipoPqrs.RECLAMO, NivelRiesgo.VITAL, None),
    (TipoPqrs.RECLAMO, NivelRiesgo.PRIORIZADO, 2),
    (TipoPqrs.RECLAMO, NivelRiesgo.PRIORIZADO, 7),
    (TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 4),
    (TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 6),
    (TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 5),
    (TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA, 1),
    (TipoPqrs.SUGERENCIA, NivelRiesgo.NO_APLICA, 1),
    (TipoPqrs.SOLICITUD_INFORMACION, NivelRiesgo.NO_APLICA, 3),
    (TipoPqrs.CONSULTA, NivelRiesgo.NO_APLICA, 1),
    (TipoPqrs.PETICION, NivelRiesgo.NO_APLICA, None),
]


@pytest.fixture(scope="module")
def demo() -> list[dict[str, Any]]:
    return json.loads(RUTA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entradas(demo: list[dict[str, Any]]) -> list[PqrsNueva]:
    return [PqrsNueva.model_validate(pqrs) for pqrs in demo]


def _datos(entrada: PqrsNueva) -> DatosPeticionario:
    p = entrada.peticionario
    return DatosPeticionario(p.tipo_documento, p.numero_documento, p.nombre, p.telefono, p.correo)


def _enmascarado(entrada: PqrsNueva) -> str:
    return EnmascaradorReglas().enmascarar(entrada.texto, _datos(entrada)).texto


def _clasificado(entrada: PqrsNueva) -> tuple[TipoPqrs, NivelRiesgo, int | None]:
    solicitud = SolicitudClasificacion(1, _enmascarado(entrada), CATALOGO, "clasif-v1.0")
    resultado = ClasificadorPalabrasClave().clasificar(solicitud)
    return resultado.tipo, resultado.nivel_riesgo, resultado.id_area


def test_tiene_entre_10_y_15_pqrs(demo: list[dict[str, Any]]) -> None:
    assert 10 <= len(demo) <= 15


def test_cada_pqrs_tiene_el_formato_de_entrada_de_la_api(entradas: list[PqrsNueva]) -> None:
    assert all(entrada.fecha_radicacion <= datetime(2026, 10, 31, tzinfo=ZONA_COLOMBIA) for entrada in entradas)


def test_los_datos_personales_son_claramente_sinteticos(demo: list[dict[str, Any]]) -> None:
    for pqrs in demo:
        peticionario = pqrs["peticionario"]
        assert re.fullmatch(r"10000000\d\d", peticionario["numeroDocumento"])
        assert re.fullmatch(r"30000000\d\d", peticionario["telefono"])
        assert peticionario["correo"].endswith("@radica.test")
        assert "Sintético" in peticionario["nombre"]
    documentos = [pqrs["peticionario"]["numeroDocumento"] for pqrs in demo]
    assert len(set(documentos)) == len(documentos)


def test_ningun_dato_personal_sobrevive_al_enmascaramiento(entradas: list[PqrsNueva]) -> None:
    enmascarador = EnmascaradorReglas()
    for entrada in entradas:
        assert enmascarador.verificar(_enmascarado(entrada), _datos(entrada)).limpio


def test_muestra_el_enmascaramiento_de_cada_tipo_de_dato(entradas: list[PqrsNueva]) -> None:
    textos = " ".join(_enmascarado(entrada) for entrada in entradas)
    for marcador in ("[CEDULA_1]", "[TELEFONO_1]", "[CORREO_1]", "[HC_1]"):
        assert marcador in textos


def test_clasificacion_esperada(entradas: list[PqrsNueva]) -> None:
    assert [_clasificado(entrada) for entrada in entradas] == ESPERADOS


def test_cubre_todos_los_tipos_y_niveles(entradas: list[PqrsNueva]) -> None:
    clasificados = [_clasificado(entrada) for entrada in entradas]
    assert {tipo for tipo, _, _ in clasificados} == set(TipoPqrs)
    assert {nivel for _, nivel, _ in clasificados} == set(NivelRiesgo)


@pytest.mark.parametrize(
    ("momento", "rojas", "amarillas", "verdes"),
    [(AVANCES, 5, 4, 3), (ENTREGA, 7, 2, 3)],
    ids=["avances-2-nov", "entrega-4-nov"],
)
def test_la_bandeja_muestra_los_tres_colores_en_las_presentaciones(
    entradas: list[PqrsNueva],
    terminos: tuple[Termino, ...],
    festivos: frozenset[date],
    momento: datetime,
    rojas: int,
    amarillas: int,
    verdes: int,
) -> None:
    colores = []
    for entrada in entradas:
        tipo, nivel, _ = _clasificado(entrada)
        termino = seleccionar_termino(
            terminos,
            tipo,
            nivel_efectivo(tipo, nivel),
            entrada.paciente_menor_de_edad,
            entrada.fecha_radicacion,
        )
        vencimiento = CalculadoraDePlazos().calcular(termino, entrada.fecha_radicacion, festivos)
        colores.append(ReglaSemaforo(0.5).evaluar(entrada.fecha_radicacion, vencimiento, momento).color)

    assert colores.count(Semaforo.ROJO) == rojas
    assert colores.count(Semaforo.AMARILLO) == amarillas
    assert colores.count(Semaforo.VERDE) == verdes
