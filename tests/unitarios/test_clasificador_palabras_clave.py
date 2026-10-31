"""ClasificadorPalabrasClave y su diccionario (contexto.md 4.5, PB-21). Textos sintéticos."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from radica.adaptadores.salida.palabras_clave.clasificador import (
    RUTA_DICCIONARIO,
    ClasificadorPalabrasClave,
)
from radica.aplicacion.puertos.clasificador import (
    AreaCatalogo,
    Catalogo,
    ClasificadorPqrs,
    ResultadoClasificacion,
    SolicitudClasificacion,
)
from radica.dominio.plazos import ZONA_COLOMBIA, Termino, nivel_efectivo, seleccionar_termino
from radica.dominio.valores import NivelRiesgo, TipoPqrs, Unidad

R = TipoPqrs.RECLAMO
Q = TipoPqrs.QUEJA
S = TipoPqrs.SUGERENCIA
I = TipoPqrs.SOLICITUD_INFORMACION
C = TipoPqrs.CONSULTA
P = TipoPqrs.PETICION
VITAL = NivelRiesgo.VITAL
PRIORIZADO = NivelRiesgo.PRIORIZADO
SIMPLE = NivelRiesgo.SIMPLE
NO_APLICA = NivelRiesgo.NO_APLICA

# Las áreas semilla de docs/modelo-datos.md (2.4).
AREAS = {
    1: "Atención al usuario",
    2: "Citas",
    3: "Archivo clínico",
    4: "Autorizaciones",
    5: "Facturación",
    6: "Farmacia",
    7: "Servicios asistenciales",
}
RADICACION = datetime(2026, 10, 30, 16, tzinfo=ZONA_COLOMBIA)

CLASIFICADOR = ClasificadorPalabrasClave()

# id, texto enmascarado, tipo, nivel y área esperados.
CASOS = [
    ("vital-literal", "El paciente está en riesgo vital y no lo atienden.", R, VITAL, None),
    ("vital-urgencias", "Mi hijo está en riesgo vital y no lo atienden en urgencias.", R, VITAL, 7),
    ("vital-convulsiones", "Mi niña de 3 años tiene convulsiones y en urgencias no la atienden.", R, VITAL, 7),
    ("vital-mayusculas", "MI PAPÁ TUVO UN INFARTO Y LA AMBULANCIA NUNCA LLEGÓ.", R, VITAL, None),
    ("vital-tildes", "Mi mamá perdió el conocimiento en la sala de espera y ningún médico la vio.", R, VITAL, 7),
    ("vital-gana-a-reclamo", "Mi hermano habla de quitarse la vida y le cancelaron la cita con psiquiatría.", R, VITAL, 2),
    ("vital-gana-a-queja", "Presento una queja: por la demora mi esposo está en peligro de muerte.", R, VITAL, None),
    ("vital-negado-sigue-vital", "La enfermera dijo que no hay riesgo vital, pero no me han dado la fórmula médica.", R, VITAL, 6),
    ("menor-simple", "A mi hijo menor de edad le negaron la autorización de la terapia.", R, SIMPLE, 4),
    ("menor-priorizado", "Mi hija de 10 años tiene cáncer y suspendieron la quimioterapia.", R, PRIORIZADO, 7),
    ("menor-solicitud", "Solicito copia del carné de vacunas de mi hijo menor.", I, NO_APLICA, None),
    ("priorizado-gestante", "Estoy embarazada y no me han dado la cita de control.", R, PRIORIZADO, 2),
    ("priorizado-dialisis", "Soy paciente de diálisis y me cancelaron la sesión.", R, PRIORIZADO, 7),
    ("priorizado-literal", "Caso de riesgo priorizado: el dolor intenso sigue y no hay agenda.", R, PRIORIZADO, 2),
    (
        "reclamo-ejemplo-del-contrato",
        "Desde hace tres semanas me ordenaron una resonancia y no me han dado la autorización."
        " Llamé dos veces y nadie responde. Mi teléfono es [TELEFONO_1].",
        R, SIMPLE, 4,
    ),
    ("reclamo-cita", "Me cancelaron la cita tres veces este mes.", R, SIMPLE, 2),
    ("reclamo-medicamentos", "No me entregaron los medicamentos completos en la farmacia.", R, SIMPLE, 6),
    ("reclamo-cobro", "Me cobraron un copago que ya había pagado en la factura anterior.", R, SIMPLE, 5),
    ("reclamo-espera", "Llevo dos meses esperando el examen de laboratorio.", R, SIMPLE, 7),
    ("queja-literal", "Presento una queja porque la recepcionista fue grosera.", Q, NO_APLICA, 1),
    ("queja-mayusculas", "El funcionario fue DESCORTÉS conmigo.", Q, NO_APLICA, 1),
    ("sugerencia", "Sugiero ampliar los horarios de la farmacia.", S, NO_APLICA, 6),
    ("solicitud", "Solicito información sobre los requisitos de afiliación.", I, NO_APLICA, None),
    ("solicitud-enmascarada", "Solicito copia de mi historia clínica [HC_1].", I, NO_APLICA, 3),
    ("consulta", "Tengo una consulta sobre cuál es el procedimiento para cambiar de sede.", C, NO_APLICA, 1),
    ("peticion-sin-coincidencia", "Quiero saber los horarios de la sede norte.", P, NO_APLICA, 1),
    ("peticion-solo-marcadores", "Necesito que me actualicen el contacto [TELEFONO_1] y [CORREO_1].", P, NO_APLICA, None),
    ("ambiguo-queja-con-demora", "Presento una queja por la demora en la cita.", R, SIMPLE, 2),
    ("ambiguo-sugerencia-con-negativa", "Sugiero que mejoren, porque me negaron la autorización.", R, SIMPLE, 4),
    ("ambiguo-consulta-es-servicio", "Necesito cambiar la fecha de mi consulta externa.", P, NO_APLICA, 7),
    ("ambiguo-felicitar-no-es-cita", "Quiero felicitar a la enfermera por su buen trato.", P, NO_APLICA, 7),
    ("ambiguo-cita-sin-falla", "Solicito información para saber cómo pido una cita.", I, NO_APLICA, 2),
    ("ambiguo-paro-no-es-cardiaco", "Por el paro de buses se canceló mi cita.", R, SIMPLE, 2),
    ("ambiguo-lucia-no-es-uci", "La señora Lucía pidió un turno en ventanilla.", P, NO_APLICA, 1),
    ("ambiguo-urgente-no-es-vital", "Necesito una cita urgente con el especialista.", P, NO_APLICA, 2),
    ("ambiguo-falsa-alarma-aceptada", "Sugiero atención preferente para adultos mayores.", R, PRIORIZADO, None),
    ("ambiguo-dos-areas", "La recepcionista de la farmacia fue grosera.", Q, NO_APLICA, 6),
]


def _catalogo(ids_areas: tuple[int, ...] = tuple(AREAS)) -> Catalogo:
    areas = tuple(AreaCatalogo(id_area, AREAS[id_area]) for id_area in ids_areas)
    return Catalogo(tipos=tuple(TipoPqrs), atributos=(), areas=areas)


def _clasificar(texto: str, catalogo: Catalogo | None = None) -> ResultadoClasificacion:
    solicitud = SolicitudClasificacion(1, texto, catalogo or _catalogo(), "clasif-v1.0")
    return CLASIFICADOR.clasificar(solicitud)


@pytest.mark.parametrize(
    ("texto", "tipo", "nivel", "area"), [caso[1:] for caso in CASOS], ids=[caso[0] for caso in CASOS]
)
def test_casos_etiquetados(texto: str, tipo: TipoPqrs, nivel: NivelRiesgo, area: int | None) -> None:
    resultado = _clasificar(texto)
    assert (resultado.tipo, resultado.nivel_riesgo, resultado.id_area) == (tipo, nivel, area)


@pytest.mark.parametrize(
    ("texto", "menor", "valor", "unidad"),
    [
        ("Mi hijo está en riesgo vital y no lo atienden en urgencias.", True, 8, Unidad.HORAS_CORRIDAS),
        ("Mi niña de 3 años tiene convulsiones y en urgencias no la atienden.", False, 24, Unidad.HORAS_CORRIDAS),
        ("Mi hija de 10 años tiene cáncer y suspendieron la quimioterapia.", True, 48, Unidad.HORAS_CORRIDAS),
        ("A mi hijo menor de edad le negaron la autorización de la terapia.", True, 72, Unidad.HORAS_CORRIDAS),
        ("Solicito copia del carné de vacunas de mi hijo menor.", True, 10, Unidad.DIAS_HABILES),
    ],
    ids=["vital-menor", "vital-sin-marca", "priorizado-menor", "simple-menor", "solicitud-menor"],
)
def test_el_plazo_de_menor_lo_decide_la_marca_y_no_el_texto(
    terminos: tuple[Termino, ...], texto: str, menor: bool, valor: int, unidad: Unidad
) -> None:
    resultado = _clasificar(texto)
    nivel = nivel_efectivo(resultado.tipo, resultado.nivel_riesgo)

    termino = seleccionar_termino(terminos, resultado.tipo, nivel, menor, RADICACION)

    assert (termino.valor, termino.unidad) == (valor, unidad)


@pytest.mark.parametrize("texto", [caso[1] for caso in CASOS], ids=[caso[0] for caso in CASOS])
def test_cumple_el_contrato_de_las_reglas(texto: str) -> None:
    resultado = _clasificar(texto)
    assert resultado.confianza == 0.5
    assert resultado.id_atributo is None
    assert resultado.uso is None
    assert resultado.resumen is None
    assert dict(resultado.datos_clave) == {}


def test_implementa_el_puerto() -> None:
    clasificador: ClasificadorPqrs = CLASIFICADOR
    solicitud = SolicitudClasificacion(1, "", _catalogo(), "clasif-v1.0")
    assert clasificador.clasificar(solicitud).tipo is TipoPqrs.PETICION


def test_las_senales_son_las_palabras_de_riesgo_encontradas() -> None:
    assert _clasificar("Tuvo un INFARTO y está en cuidados intensivos.").senales_riesgo == (
        "infarto",
        "cuidados intensivos",
    )
    assert _clasificar("Estoy embarazada y tengo dolor intenso.").senales_riesgo == (
        "embarazada",
        "dolor intenso",
    )
    assert _clasificar("Me cancelaron la cita tres veces este mes.").senales_riesgo == ()
    assert _clasificar("Presento una queja por el mal trato.").senales_riesgo == ()


def test_tolera_varios_espacios_dentro_de_una_expresion() -> None:
    assert _clasificar("Está en  riesgo\nvital desde ayer.").nivel_riesgo is NivelRiesgo.VITAL


def test_solo_sugiere_areas_del_catalogo_de_la_solicitud() -> None:
    texto = "Le negaron la autorización de la cita."
    assert _clasificar(texto).id_area == 4
    assert _clasificar(texto, _catalogo((1, 2, 3))).id_area == 2
    assert _clasificar(texto, _catalogo((1, 3))).id_area is None


def test_el_diccionario_usa_las_areas_del_modelo_de_datos() -> None:
    diccionario = json.loads(RUTA_DICCIONARIO.read_text(encoding="utf-8"))
    assert {area["id_area"]: area["nombre"] for area in diccionario["areas"]} == AREAS


@pytest.mark.parametrize(
    "contenido",
    [
        {},
        {"version": "1.0"},
        {"version": "1.0", "vital": []},
        {"version": "1.0", "vital": ["  "]},
    ],
    ids=["sin-version", "sin-listas", "lista-vacia", "texto-vacio"],
)
def test_rechaza_un_diccionario_invalido(tmp_path: Path, contenido: dict[str, object]) -> None:
    ruta = tmp_path / "diccionario.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ValueError, match="Diccionario inválido"):
        ClasificadorPalabrasClave(ruta)


def test_rechaza_un_diccionario_sin_areas(tmp_path: Path) -> None:
    contenido = json.loads(RUTA_DICCIONARIO.read_text(encoding="utf-8"))
    del contenido["areas"]
    ruta = tmp_path / "diccionario.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ValueError, match="areas"):
        ClasificadorPalabrasClave(ruta)
