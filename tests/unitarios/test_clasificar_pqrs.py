"""ClasificarPqrs con dobles en memoria y un clasificador falso, sin red (contexto.md 4.4, 4.9 y 4.12).

Cada escenario registra primero la PQRS con RegistrarPqrs, como en la API, y
luego la clasifica como lo haría el trabajador.
"""

import os
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest
from dobles import (
    CATALOGO,
    AuditoriaEnMemoria,
    ClasificadorFijo,
    ClasificadorQueFalla,
    ConfiguracionEnMemoria,
    PqrsEnMemoria,
)

from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.aplicacion.casos_de_uso.clasificar_pqrs import ClasificarPqrs
from radica.aplicacion.casos_de_uso.errores import PqrsNoEncontrada
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs, SolicitudRegistro
from radica.aplicacion.puertos.clasificador import (
    ClasificadorPqrs,
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    UsoIA,
)
from radica.aplicacion.puertos.enmascarador import TextoEnmascarado
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos, Termino
from radica.dominio.riesgo import PoliticaDeRiesgo
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    ResultadoLlamadaIA,
    TipoDocumento,
    TipoPqrs,
)

RADICACION = datetime(2026, 10, 30, 16, tzinfo=ZONA_COLOMBIA)
AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
TELEFONO = "3000000000"
NOMBRE = "Usuaria Sintética Dos"
PETICIONARIO = DatosPeticionario(
    TipoDocumento.CC, "1000000002", NOMBRE, TELEFONO, "usuaria2@ejemplo.com"
)
TEXTO = (
    "Desde hace tres semanas me ordenaron una resonancia y no me han dado la autorización."
    f" Mi teléfono es {TELEFONO}."
)


def _uso(intento: int = 1, resultado: ResultadoLlamadaIA = ResultadoLlamadaIA.OK) -> UsoIA:
    return UsoIA("anthropic", "claude-haiku-5-5", 900, 120, Decimal("0.00015"), 800, intento, resultado)


def _ia(tipo: TipoPqrs, nivel: NivelRiesgo, confianza: float = 0.9, **otros: object) -> ResultadoClasificacion:
    campos: dict[str, object] = {
        "tipo": tipo,
        "id_atributo": 2,
        "id_area": 4,
        "nivel_riesgo": nivel,
        "confianza": confianza,
        "resumen": "Paciente espera hace tres semanas la autorización de una resonancia.",
        "datos_clave": {"servicio": "resonancia"},
        "uso": _uso(),
    }
    return ResultadoClasificacion(**(campos | otros))  # type: ignore[arg-type]


def _reglas(tipo: TipoPqrs, nivel: NivelRiesgo) -> ResultadoClasificacion:
    return ResultadoClasificacion(tipo=tipo, id_atributo=None, id_area=4, nivel_riesgo=nivel, confianza=0.5)


QUEJA_IA = _ia(TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA)


class SinEnmascarar:
    """Enmascarador defectuoso para el registro: deja el texto como llegó."""

    def enmascarar(self, texto: str, datos: DatosPeticionario) -> TextoEnmascarado:
        return TextoEnmascarado(texto, ())

    def verificar(self, texto_enmascarado: str, datos: DatosPeticionario):  # pragma: no cover
        raise AssertionError("El registro no verifica")


class Escenario:
    def __init__(
        self,
        terminos: tuple[Termino, ...],
        festivos: frozenset[date],
        provisional: ResultadoClasificacion,
        clasificador: ClasificadorPqrs | None,
        registro_enmascara: bool = True,
    ) -> None:
        self.pqrs = PqrsEnMemoria()
        self.auditoria = AuditoriaEnMemoria()
        self.configuracion = ConfiguracionEnMemoria(terminos, festivos)
        self.cifrador = CifradorAesGcm(os.urandom(32), os.urandom(32))
        self.clasificador = clasificador
        self.registrar = RegistrarPqrs(
            pqrs=self.pqrs,
            auditoria=self.auditoria,
            configuracion=self.configuracion,
            cifrador=self.cifrador,
            enmascarador=EnmascaradorReglas() if registro_enmascara else SinEnmascarar(),
            clasificador_provisional=ClasificadorFijo(provisional),
            calculadora=CalculadoraDePlazos(),
            semaforo=ReglaSemaforo(0.5),
            reloj=lambda: AHORA,
            id_usuario_actor=1,
            version_instrucciones="clasif-v1.0",
        )
        self.caso = ClasificarPqrs(
            pqrs=self.pqrs,
            auditoria=self.auditoria,
            configuracion=self.configuracion,
            cifrador=self.cifrador,
            enmascarador=EnmascaradorReglas(),
            clasificador=clasificador,
            calculadora=CalculadoraDePlazos(),
            politica=PoliticaDeRiesgo(0.75),
            version_instrucciones="clasif-v1.0",
        )

    def registrar_pqrs(self, texto: str = TEXTO, menor: bool = False) -> int:
        solicitud = SolicitudRegistro(Canal.DIME, None, RADICACION, texto, menor, PETICIONARIO)
        return self.registrar.ejecutar(solicitud).pqrs.id

    def eventos(self, id_pqrs: int, desde: int = 0) -> list:
        """Eventos de la PQRS a partir de la posición desde (los del registro van antes)."""
        return self.auditoria.historial(id_pqrs)[desde:]


def _crear(terminos, festivos, provisional, clasificador, **otros) -> tuple[Escenario, int, int]:
    escenario = Escenario(terminos, festivos, provisional, clasificador, **otros)
    id_pqrs = escenario.registrar_pqrs()
    return escenario, id_pqrs, len(escenario.auditoria.historial(id_pqrs))


def _campos(eventos: list) -> list[tuple]:
    return [(e.accion, e.origen, e.campo, e.valor_anterior, e.valor_nuevo) for e in eventos]


# --- Los seis casos de prueba de contexto.md 4.9 ---

def test_la_ia_sube_simple_a_priorizado_y_el_plazo_pasa_de_72_a_48_horas(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.PRIORIZADO, senales_riesgo=("dolor intenso",)))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)
    antes = escenario.pqrs.pqrs[id_pqrs]
    assert antes.fecha_vencimiento == datetime(2026, 11, 2, 16, tzinfo=ZONA_COLOMBIA)

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.COMPLETADA

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert pqrs.nivel_riesgo is NivelRiesgo.PRIORIZADO
    assert pqrs.id_termino == 7
    assert pqrs.fecha_vencimiento == datetime(2026, 11, 1, 16, tzinfo=ZONA_COLOMBIA)
    assert pqrs.id_atributo == 2
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.CLASIFICADA, EstadoIa.COMPLETADA)

    reglas, sugerencia = escenario.pqrs.de(id_pqrs)
    assert reglas.origen is OrigenClasificacion.REGLAS and not reglas.vigente
    assert sugerencia.origen is OrigenClasificacion.IA and sugerencia.vigente
    assert sugerencia.id_llamada_ia == 1
    assert sugerencia.resumen.startswith("Paciente espera")
    assert dict(sugerencia.datos_extraidos) == {"servicio": "resonancia"}
    assert escenario.auditoria.llamadas == [(id_pqrs, _uso(), "clasif-v1.0")]

    eventos = escenario.eventos(id_pqrs, previos)
    assert _campos(eventos) == [
        (AccionAuditoria.CLASIFICAR_IA, OrigenEvento.IA, "id_atributo", None, "2"),
        (AccionAuditoria.CLASIFICAR_IA, OrigenEvento.IA, "nivel_riesgo", "SIMPLE", "PRIORIZADO"),
        (AccionAuditoria.CLASIFICAR_IA, OrigenEvento.IA, "estado", "REGISTRADA", "CLASIFICADA"),
        (
            AccionAuditoria.CALCULAR_VENCIMIENTO,
            OrigenEvento.SISTEMA,
            "fecha_vencimiento",
            "2026-11-02T16:00:00-05:00",
            "2026-11-01T16:00:00-05:00",
        ),
    ]
    assert eventos[1].motivo == (
        "Sugerencia de la IA aplicada (confianza 0,90). Señales de riesgo: dolor intenso."
    )
    assert eventos[3].motivo == "Reclamo en salud, riesgo priorizado: 48 horas corridas"


def test_la_ia_baja_vital_a_simple_no_cambia_nada_y_pide_revision(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.VITAL), ia)
    antes = escenario.pqrs.pqrs[id_pqrs]

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.COMPLETADA

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert replace(pqrs, estado=antes.estado, estado_ia=antes.estado_ia) == antes
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.COMPLETADA)
    reglas, sugerencia = escenario.pqrs.de(id_pqrs)
    assert reglas.vigente and not sugerencia.vigente
    assert sugerencia.nivel_riesgo is NivelRiesgo.SIMPLE and sugerencia.id_llamada_ia == 1

    (evento,) = escenario.eventos(id_pqrs, previos)
    assert (evento.accion, evento.origen, evento.campo, evento.valor_anterior, evento.valor_nuevo) == (
        AccionAuditoria.SUGERENCIA_IA_NO_APLICADA,
        OrigenEvento.SISTEMA,
        "estado",
        "REGISTRADA",
        "REQUIERE_REVISION",
    )
    assert evento.motivo == (
        "La sugerencia de la IA alargaría el plazo vigente."
        " Sugería RECLAMO con riesgo SIMPLE (confianza 0,90)."
    )


def test_la_ia_cambia_peticion_por_solicitud_de_informacion_y_queda_vigente(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.SOLICITUD_INFORMACION, NivelRiesgo.NO_APLICA, id_atributo=None))
    escenario, id_pqrs, previos = _crear(
        terminos, festivos, _reglas(TipoPqrs.PETICION, NivelRiesgo.NO_APLICA), ia
    )

    escenario.caso.ejecutar(id_pqrs)

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert pqrs.tipo is TipoPqrs.SOLICITUD_INFORMACION
    assert pqrs.id_termino == 2
    assert pqrs.fecha_vencimiento == datetime(2026, 11, 17, 23, 59, 59, tzinfo=ZONA_COLOMBIA)
    assert pqrs.estado is EstadoPqrs.CLASIFICADA
    assert _campos(escenario.eventos(id_pqrs, previos))[0] == (
        AccionAuditoria.CLASIFICAR_IA, OrigenEvento.IA, "tipo", "PETICION", "SOLICITUD_INFORMACION"
    )


def test_confianza_0_6_queda_vigente_pero_requiere_revision(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, confianza=0.6))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    assert escenario.pqrs.vigente(id_pqrs).origen is OrigenClasificacion.IA
    assert escenario.pqrs.pqrs[id_pqrs].estado is EstadoPqrs.REQUIERE_REVISION
    estado = [e for e in escenario.eventos(id_pqrs, previos) if e.campo == "estado"]
    assert [(e.valor_nuevo, e.motivo) for e in estado] == [
        ("REQUIERE_REVISION", "Confianza 0,60 menor al umbral 0,75.")
    ]


def test_proveedor_caido_deja_fallida_y_requiere_revision(terminos, festivos) -> None:
    intentos = tuple(_uso(n, ResultadoLlamadaIA.TIMEOUT) for n in (1, 2, 3))
    caido = ClasificadorQueFalla(ProveedorNoDisponible("sin respuesta", intentos))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), caido)
    antes = escenario.pqrs.pqrs[id_pqrs]

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.FALLIDA

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.FALLIDA)
    assert pqrs.fecha_vencimiento == antes.fecha_vencimiento
    assert [c.origen for c in escenario.pqrs.de(id_pqrs)] == [OrigenClasificacion.REGLAS]
    assert escenario.pqrs.vigente(id_pqrs).origen is OrigenClasificacion.REGLAS
    assert [uso.intento for _, uso, _ in escenario.auditoria.llamadas] == [1, 2, 3]
    eventos = escenario.eventos(id_pqrs, previos)
    assert _campos(eventos) == [
        (AccionAuditoria.IA_FALLIDA, OrigenEvento.SISTEMA, "estado_ia", "PENDIENTE", "FALLIDA"),
        (AccionAuditoria.IA_FALLIDA, OrigenEvento.SISTEMA, "estado", "REGISTRADA", "REQUIERE_REVISION"),
    ]
    assert {evento.motivo for evento in eventos} == {
        "El proveedor de IA no dio una clasificación válida (TIMEOUT)."
        " Sigue vigente la clasificación por reglas."
    }


def test_enmascaramiento_no_verificado_omite_la_ia_sin_ninguna_llamada(terminos, festivos) -> None:
    # Criterio 2 de HU-03: el registro dejó el teléfono y la IA no se llama.
    espia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.VITAL))
    escenario, id_pqrs, previos = _crear(
        terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), espia, registro_enmascara=False
    )

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.OMITIDA

    assert espia.solicitudes == []
    assert escenario.auditoria.llamadas == []
    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.OMITIDA)
    eventos = escenario.eventos(id_pqrs, previos)
    assert _campos(eventos) == [
        (AccionAuditoria.IA_OMITIDA, OrigenEvento.SISTEMA, "estado_ia", "PENDIENTE", "OMITIDA"),
        (AccionAuditoria.IA_OMITIDA, OrigenEvento.SISTEMA, "estado", "REGISTRADA", "REQUIERE_REVISION"),
    ]
    assert {evento.motivo for evento in eventos} == {
        "Enmascaramiento no verificado: quedan datos de tipo TELEFONO. No se llamó a la IA."
    }
    assert all(TELEFONO not in evento.motivo for evento in eventos)


# --- Verificación (4.4) y modo sin IA ---

def test_la_verificacion_usa_los_datos_descifrados_del_peticionario(terminos, festivos) -> None:
    # Ningún detector reconoce nombres: solo el valor que dio el peticionario delata el nombre.
    espia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE))
    escenario = Escenario(
        terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), espia, registro_enmascara=False
    )
    id_pqrs = escenario.registrar_pqrs(f"Soy {NOMBRE} y no me han dado la autorización del examen.")

    escenario.caso.ejecutar(id_pqrs)

    assert espia.solicitudes == []
    assert escenario.auditoria.historial(id_pqrs)[-1].motivo == (
        "Enmascaramiento no verificado: quedan datos de tipo NOMBRE. No se llamó a la IA."
    )


def test_con_ia_desactivada_omite_sin_llamar_y_deja_las_reglas(terminos, festivos) -> None:
    escenario, id_pqrs, previos = _crear(
        terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), clasificador=None
    )

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.OMITIDA

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.OMITIDA)
    assert escenario.pqrs.vigente(id_pqrs).origen is OrigenClasificacion.REGLAS
    eventos = escenario.eventos(id_pqrs, previos)
    assert [evento.campo for evento in eventos] == ["estado_ia", "estado"]
    assert {(evento.accion, evento.motivo) for evento in eventos} == {
        (AccionAuditoria.IA_OMITIDA, "IA desactivada por configuración")
    }


def test_al_omitir_de_nuevo_una_pqrs_que_ya_pedia_revision_solo_cambia_estado_ia(
    terminos, festivos
) -> None:
    escenario, id_pqrs, _ = _crear(
        terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), clasificador=None
    )
    escenario.caso.ejecutar(id_pqrs)
    assert escenario.pqrs.marcar_pendiente(id_pqrs, EstadoIa.OMITIDA)  # el reintento manual
    previos = len(escenario.auditoria.historial(id_pqrs))

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.OMITIDA

    assert _campos(escenario.eventos(id_pqrs, previos)) == [
        (AccionAuditoria.IA_OMITIDA, OrigenEvento.SISTEMA, "estado_ia", "PENDIENTE", "OMITIDA")
    ]


def test_la_solicitud_lleva_el_texto_enmascarado_el_catalogo_y_la_version(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE))
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    (solicitud,) = ia.solicitudes
    assert solicitud.id_pqrs == id_pqrs
    assert solicitud.texto_enmascarado == escenario.pqrs.pqrs[id_pqrs].texto_enmascarado
    assert "[TELEFONO_1]" in solicitud.texto_enmascarado and TELEFONO not in solicitud.texto_enmascarado
    assert solicitud.catalogo == CATALOGO
    assert solicitud.version_instrucciones == "clasif-v1.0"


# --- Respaldo, salida inválida y llamadas ---

def test_si_responde_el_respaldo_queda_fallida_y_se_guardan_los_intentos(terminos, festivos) -> None:
    fallidos = (_uso(1, ResultadoLlamadaIA.ERROR_PROVEEDOR), _uso(2, ResultadoLlamadaIA.ERROR_PROVEEDOR))
    respaldo = ClasificadorFijo(
        replace(_reglas(TipoPqrs.RECLAMO, NivelRiesgo.VITAL), intentos_fallidos=fallidos)
    )
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), respaldo)

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.FALLIDA

    assert escenario.pqrs.pqrs[id_pqrs].nivel_riesgo is NivelRiesgo.SIMPLE
    assert len(escenario.pqrs.de(id_pqrs)) == 1
    assert [uso.resultado for _, uso, _ in escenario.auditoria.llamadas] == [
        ResultadoLlamadaIA.ERROR_PROVEEDOR, ResultadoLlamadaIA.ERROR_PROVEEDOR
    ]
    assert "(ERROR_PROVEEDOR)" in escenario.auditoria.historial(id_pqrs)[-1].motivo


def test_salida_invalida_queda_fallida(terminos, festivos) -> None:
    intentos = (_uso(1, ResultadoLlamadaIA.SALIDA_INVALIDA), _uso(2, ResultadoLlamadaIA.SALIDA_INVALIDA))
    invalida = ClasificadorQueFalla(SalidaInvalida("fuera del catálogo", intentos))
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA), invalida)

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.FALLIDA
    assert len(escenario.auditoria.llamadas) == 2


def test_los_intentos_fallidos_previos_se_guardan_antes_que_el_ok(terminos, festivos) -> None:
    ia = ClasificadorFijo(
        _ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, uso=_uso(2), intentos_fallidos=(_uso(1, ResultadoLlamadaIA.TIMEOUT),))
    )
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    assert [(uso.intento, uso.resultado) for _, uso, _ in escenario.auditoria.llamadas] == [
        (1, ResultadoLlamadaIA.TIMEOUT), (2, ResultadoLlamadaIA.OK)
    ]
    assert escenario.pqrs.vigente(id_pqrs).id_llamada_ia == 2


# --- Eventos y bordes ---

def test_si_la_ia_coincide_con_las_reglas_solo_cambia_el_estado(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, id_atributo=None))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    assert _campos(escenario.eventos(id_pqrs, previos)) == [
        (AccionAuditoria.CLASIFICAR_IA, OrigenEvento.IA, "estado", "REGISTRADA", "CLASIFICADA")
    ]


def test_el_cambio_de_area_sugerida_queda_auditado(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, id_atributo=None, id_area=2))
    escenario, id_pqrs, previos = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    assert ("id_area", "4", "2") in [
        (e.campo, e.valor_anterior, e.valor_nuevo) for e in escenario.eventos(id_pqrs, previos)
    ]


def test_el_motivo_no_pasa_de_300_caracteres(terminos, festivos) -> None:
    senales = tuple(f"señal de riesgo número {n}" for n in range(30))
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.VITAL, senales_riesgo=senales))
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)

    escenario.caso.ejecutar(id_pqrs)

    motivo = next(e.motivo for e in escenario.auditoria.historial(id_pqrs) if e.campo == "nivel_riesgo"
                  and e.accion is AccionAuditoria.CLASIFICAR_IA)
    assert len(motivo) == 300 and motivo.endswith("…")


def test_un_menor_con_riesgo_vital_queda_con_8_horas(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.VITAL))
    escenario = Escenario(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)
    id_pqrs = escenario.registrar_pqrs(menor=True)

    escenario.caso.ejecutar(id_pqrs)

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert pqrs.id_termino == 9
    assert pqrs.fecha_vencimiento == datetime(2026, 10, 31, 0, tzinfo=ZONA_COLOMBIA)


# --- Selección de la PQRS ---

def test_tomar_siguiente_da_la_mas_antigua_y_luego_no_hay_mas(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE))
    escenario = Escenario(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)
    primera, segunda = escenario.registrar_pqrs(), escenario.registrar_pqrs()

    for esperada in (primera, segunda):
        assert escenario.caso.tomar_siguiente() == esperada
        escenario.caso.ejecutar(esperada)
    assert escenario.caso.tomar_siguiente() is None
    assert len(ia.solicitudes) == 2


def test_un_error_interno_deja_fallida_para_no_volver_a_tomarla(terminos, festivos) -> None:
    escenario, id_pqrs, previos = _crear(
        terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ClasificadorFijo(QUEJA_IA)
    )

    escenario.caso.registrar_error_interno(id_pqrs)
    escenario.caso.registrar_error_interno(id_pqrs)  # la segunda vez ya no está pendiente

    pqrs = escenario.pqrs.pqrs[id_pqrs]
    assert (pqrs.estado, pqrs.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.FALLIDA)
    eventos = escenario.eventos(id_pqrs, previos)
    assert [evento.campo for evento in eventos] == ["estado_ia", "estado"]
    assert {(evento.accion, evento.motivo) for evento in eventos} == {
        (AccionAuditoria.IA_FALLIDA, "Error interno al clasificar. Sigue vigente la clasificación por reglas.")
    }
    assert escenario.caso.tomar_siguiente() is None


def test_una_pqrs_que_ya_no_esta_pendiente_no_se_vuelve_a_clasificar(terminos, festivos) -> None:
    ia = ClasificadorFijo(_ia(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE))
    escenario, id_pqrs, _ = _crear(terminos, festivos, _reglas(TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE), ia)
    escenario.caso.ejecutar(id_pqrs)

    assert escenario.caso.ejecutar(id_pqrs) is EstadoIa.COMPLETADA
    assert len(ia.solicitudes) == 1


def test_una_pqrs_inexistente_falla(terminos, festivos) -> None:
    escenario = Escenario(terminos, festivos, _reglas(TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA), None)
    with pytest.raises(PqrsNoEncontrada):
        escenario.caso.ejecutar(999)
