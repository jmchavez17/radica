"""SolicitarClasificacion: reintento manual de la IA con dobles en memoria (contexto.md 4.10 y 4.12)."""

import os
from datetime import datetime

import pytest
from dobles import AuditoriaEnMemoria, ClasificadorFijo, ConfiguracionEnMemoria, PqrsEnMemoria

from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.aplicacion.casos_de_uso.errores import OperacionNoPermitida, PqrsNoEncontrada
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs, SolicitudRegistro
from radica.aplicacion.casos_de_uso.solicitar_clasificacion import SolicitarClasificacion
from radica.aplicacion.puertos.clasificador import ResultadoClasificacion
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenEvento,
    TipoDocumento,
    TipoPqrs,
)

AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)


@pytest.fixture
def escenario(terminos, festivos):
    pqrs, auditoria = PqrsEnMemoria(), AuditoriaEnMemoria()
    registrar = RegistrarPqrs(
        pqrs, auditoria, ConfiguracionEnMemoria(terminos, festivos),
        CifradorAesGcm(os.urandom(32), os.urandom(32)), EnmascaradorReglas(),
        ClasificadorFijo(ResultadoClasificacion(TipoPqrs.QUEJA, None, 1, NivelRiesgo.NO_APLICA, 0.5)),
        CalculadoraDePlazos(), ReglaSemaforo(0.5), lambda: AHORA, 1, "clasif-v1.0",
    )
    solicitud = SolicitudRegistro(
        Canal.WEB, None, AHORA, "El médico fue grosero en la consulta de ayer.", False,
        DatosPeticionario(TipoDocumento.CC, "1000000003", "Usuario Sintético Tres"),
    )
    id_pqrs = registrar.ejecutar(solicitud).pqrs.id
    return pqrs, auditoria, id_pqrs, SolicitarClasificacion(pqrs, auditoria, id_usuario_actor=1)


@pytest.mark.parametrize("anterior", [EstadoIa.COMPLETADA, EstadoIa.FALLIDA, EstadoIa.OMITIDA])
def test_vuelve_a_dejar_pendiente_y_registra_el_reintento(escenario, anterior: EstadoIa) -> None:
    pqrs, auditoria, id_pqrs, caso = escenario
    pqrs.actualizar_estado(id_pqrs, EstadoPqrs.REQUIERE_REVISION, anterior)

    assert caso.ejecutar(id_pqrs) is EstadoIa.PENDIENTE

    assert pqrs.pqrs[id_pqrs].estado_ia is EstadoIa.PENDIENTE
    assert pqrs.pqrs[id_pqrs].estado is EstadoPqrs.REQUIERE_REVISION  # no cambia el estado de gestión
    evento = auditoria.historial(id_pqrs)[-1]
    assert (evento.accion, evento.origen, evento.id_usuario) == (
        AccionAuditoria.REINTENTO_IA, OrigenEvento.PERSONA, 1,
    )
    assert (evento.campo, evento.valor_anterior, evento.valor_nuevo) == ("estado_ia", anterior.value, "PENDIENTE")


def test_si_ya_esta_pendiente_responde_conflicto_sin_evento(escenario) -> None:
    _, auditoria, id_pqrs, caso = escenario
    eventos = len(auditoria.eventos)

    with pytest.raises(OperacionNoPermitida, match="ya está pendiente"):
        caso.ejecutar(id_pqrs)
    assert len(auditoria.eventos) == eventos


@pytest.mark.parametrize("estado", [EstadoPqrs.RESPONDIDA, EstadoPqrs.CERRADA])
def test_una_pqrs_respondida_o_cerrada_no_se_reclasifica(escenario, estado: EstadoPqrs) -> None:
    pqrs, _, id_pqrs, caso = escenario
    pqrs.actualizar_estado(id_pqrs, estado, EstadoIa.COMPLETADA)

    with pytest.raises(OperacionNoPermitida, match=f"en estado {estado.value}"):
        caso.ejecutar(id_pqrs)
    assert pqrs.pqrs[id_pqrs].estado_ia is EstadoIa.COMPLETADA


def test_si_otro_la_dejo_pendiente_antes_responde_conflicto(escenario) -> None:
    pqrs, auditoria, id_pqrs, caso = escenario
    pqrs.actualizar_estado(id_pqrs, EstadoPqrs.CLASIFICADA, EstadoIa.COMPLETADA)
    eventos = len(auditoria.eventos)
    pqrs.marcar_pendiente = lambda *_: False  # simula la carrera: otra solicitud ganó

    with pytest.raises(OperacionNoPermitida, match="ya está pendiente"):
        caso.ejecutar(id_pqrs)
    assert len(auditoria.eventos) == eventos


def test_una_pqrs_inexistente_es_404(escenario) -> None:
    *_, caso = escenario
    with pytest.raises(PqrsNoEncontrada):
        caso.ejecutar(999)
