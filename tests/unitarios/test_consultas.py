"""Casos de uso de consulta con dobles en memoria (contexto.md 4.10)."""

from datetime import date, datetime, timedelta

import pytest
from dobles import AuditoriaEnMemoria, ConfiguracionEnMemoria, PqrsEnMemoria

from radica.aplicacion.casos_de_uso.consultas import (
    ConsultarHistorial,
    ConsultarPqrs,
    ListarBandeja,
    ListarTerminos,
)
from radica.aplicacion.casos_de_uso.errores import PqrsNoEncontrada
from radica.aplicacion.puertos.pqrs import ClasificacionVigente, FiltroBandeja, VistaPqrs
from radica.dominio.plazos import ZONA_COLOMBIA, Termino
from radica.dominio.pqrs import EventoAuditoria, Referencia
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    Semaforo,
    TipoPqrs,
)

AHORA = datetime(2026, 10, 31, 19, 30, tzinfo=ZONA_COLOMBIA)
SEMAFORO = ReglaSemaforo(0.5)


def _vista(
    id_pqrs: int,
    termino: Termino,
    horas_desde_radicacion: float,
    horas_de_plazo: float,
    estado: EstadoPqrs = EstadoPqrs.REGISTRADA,
    id_area: int | None = None,
) -> VistaPqrs:
    radicacion = AHORA - timedelta(hours=horas_desde_radicacion)
    area = Referencia(id_area, f"Área {id_area}") if id_area else None
    return VistaPqrs(
        id=id_pqrs,
        radicado=f"RAD-2026-{id_pqrs:06d}",
        canal=Canal.WEB,
        sede=None,
        fecha_radicacion=radicacion,
        texto_enmascarado="Texto sintético enmascarado",
        tipo=termino.tipo_pqrs,
        nivel_riesgo=termino.nivel_riesgo,
        estado=estado,
        estado_ia=EstadoIa.PENDIENTE,
        fecha_vencimiento=radicacion + timedelta(hours=horas_de_plazo),
        termino=termino,
        clasificacion=ClasificacionVigente(
            OrigenClasificacion.REGLAS, termino.tipo_pqrs, None, area, termino.nivel_riesgo, 0.5
        ),
    )


@pytest.fixture
def repositorio(terminos: tuple[Termino, ...]) -> PqrsEnMemoria:
    peticion, simple, priorizado = terminos[0], terminos[5], terminos[6]
    repositorio = PqrsEnMemoria()
    for vista in (
        _vista(1, peticion, 10, 400),  # verde
        _vista(2, priorizado, 27.5, 48, id_area=4),  # amarillo: quedan 20,5 h
        _vista(3, simple, 80, 72, id_area=4),  # rojo: venció hace 8 h
        _vista(4, simple, 1, 72, estado=EstadoPqrs.REQUIERE_REVISION, id_area=2),  # verde
        _vista(5, priorizado, 50, 48),  # rojo: venció hace 2 h
    ):
        repositorio.agregar_vista(vista)
    return repositorio


def _bandeja(repositorio: PqrsEnMemoria) -> ListarBandeja:
    return ListarBandeja(repositorio, SEMAFORO, lambda: AHORA)


def test_consultar_calcula_el_semaforo_al_consultar(repositorio: PqrsEnMemoria) -> None:
    consulta = ConsultarPqrs(repositorio, SEMAFORO, lambda: AHORA).ejecutar(2)

    assert consulta.pqrs.radicado == "RAD-2026-000002"
    assert (consulta.semaforo.color, consulta.semaforo.horas_restantes) == (Semaforo.AMARILLO, 20.5)


def test_consultar_una_pqrs_que_no_existe(repositorio: PqrsEnMemoria) -> None:
    with pytest.raises(PqrsNoEncontrada):
        ConsultarPqrs(repositorio, SEMAFORO, lambda: AHORA).ejecutar(999)


def test_la_bandeja_pone_las_vencidas_primero(repositorio: PqrsEnMemoria) -> None:
    pagina = _bandeja(repositorio).ejecutar(FiltroBandeja(), None, 1, 20)

    assert [elemento.pqrs.id for elemento in pagina.elementos] == [3, 5, 2, 4, 1]
    assert [elemento.semaforo.color for elemento in pagina.elementos] == [
        Semaforo.ROJO, Semaforo.ROJO, Semaforo.AMARILLO, Semaforo.VERDE, Semaforo.VERDE,
    ]
    assert (pagina.pagina, pagina.total) == (1, 5)


def test_la_bandeja_pagina(repositorio: PqrsEnMemoria) -> None:
    bandeja = _bandeja(repositorio)

    segunda = bandeja.ejecutar(FiltroBandeja(), None, 2, 2)
    assert ([e.pqrs.id for e in segunda.elementos], segunda.total) == ([2, 4], 5)

    fuera = bandeja.ejecutar(FiltroBandeja(), None, 4, 2)
    assert (fuera.elementos, fuera.total) == ([], 5)


@pytest.mark.parametrize(
    ("semaforo", "esperados"),
    [(Semaforo.ROJO, [3, 5]), (Semaforo.AMARILLO, [2]), (Semaforo.VERDE, [4, 1])],
)
def test_la_bandeja_filtra_por_semaforo(
    repositorio: PqrsEnMemoria, semaforo: Semaforo, esperados: list[int]
) -> None:
    pagina = _bandeja(repositorio).ejecutar(FiltroBandeja(), semaforo, 1, 20)
    assert ([e.pqrs.id for e in pagina.elementos], pagina.total) == (esperados, len(esperados))


def test_la_bandeja_combina_filtros(repositorio: PqrsEnMemoria) -> None:
    filtro = FiltroBandeja(tipo=TipoPqrs.RECLAMO, id_area=4)
    pagina = _bandeja(repositorio).ejecutar(filtro, Semaforo.ROJO, 1, 20)
    assert [e.pqrs.id for e in pagina.elementos] == [3]

    pagina = _bandeja(repositorio).ejecutar(FiltroBandeja(estado=EstadoPqrs.REQUIERE_REVISION), None, 1, 20)
    assert [e.pqrs.id for e in pagina.elementos] == [4]


def test_la_bandeja_rechaza_pagina_cero(repositorio: PqrsEnMemoria) -> None:
    with pytest.raises(ValueError):
        _bandeja(repositorio).ejecutar(FiltroBandeja(), None, 0, 20)


def test_historial_de_una_pqrs(repositorio: PqrsEnMemoria) -> None:
    auditoria = AuditoriaEnMemoria()
    auditoria.registrar(EventoAuditoria(1, OrigenEvento.PERSONA, AccionAuditoria.REGISTRAR, id_usuario=1))
    auditoria.registrar(EventoAuditoria(2, OrigenEvento.PERSONA, AccionAuditoria.REGISTRAR, id_usuario=1))
    auditoria.registrar(EventoAuditoria(1, OrigenEvento.SISTEMA, AccionAuditoria.CALCULAR_VENCIMIENTO))

    eventos = ConsultarHistorial(repositorio, auditoria).ejecutar(1)

    assert [evento.accion for evento in eventos] == [
        AccionAuditoria.REGISTRAR, AccionAuditoria.CALCULAR_VENCIMIENTO,
    ]


def test_historial_de_una_pqrs_que_no_existe(repositorio: PqrsEnMemoria) -> None:
    with pytest.raises(PqrsNoEncontrada):
        ConsultarHistorial(repositorio, AuditoriaEnMemoria()).ejecutar(999)


def test_terminos_vigentes_hoy(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    configuracion = ConfiguracionEnMemoria(terminos, festivos)

    assert len(ListarTerminos(configuracion, lambda: AHORA).ejecutar()) == 9
    antes = datetime(2026, 6, 8, 12, tzinfo=ZONA_COLOMBIA)
    vigentes = ListarTerminos(configuracion, lambda: antes).ejecutar()
    assert NivelRiesgo.VITAL in {t.nivel_riesgo for t in vigentes} and len(vigentes) == 8
