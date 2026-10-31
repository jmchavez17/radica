"""RegistrarPqrs con dobles en memoria (contexto.md 4.1 a 4.8 y 4.12)."""

import hashlib
import hmac
import json
import os
from dataclasses import replace
from datetime import date, datetime

import pytest
from dobles import AuditoriaEnMemoria, ClasificadorFijo, ConfiguracionEnMemoria, PqrsEnMemoria

from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.aplicacion.casos_de_uso.errores import DatosInvalidos
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs, SolicitudRegistro
from radica.aplicacion.puertos.clasificador import ResultadoClasificacion
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos, Termino, TerminoNoConfigurado
from radica.dominio.pqrs import Referencia, formato_radicado
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
    TipoDocumento,
    TipoPqrs,
)

LLAVE_CIFRADO = os.urandom(32)
LLAVE_HMAC = os.urandom(32)
AHORA = datetime(2026, 10, 30, 18, tzinfo=ZONA_COLOMBIA)
TEXTO = (
    "Desde hace tres semanas me ordenaron una resonancia y no me han dado la autorización."
    " Llamé dos veces y nadie responde. Mi teléfono es 3000000000."
)
PETICIONARIO = DatosPeticionario(
    TipoDocumento.CC, "1000000001", "Usuario Sintético Uno", "3000000000", "usuario1@ejemplo.com"
)
RECLAMO_AUTORIZACION = ResultadoClasificacion(
    tipo=TipoPqrs.RECLAMO, id_atributo=2, id_area=4, nivel_riesgo=NivelRiesgo.SIMPLE, confianza=0.5
)


SOLICITUD = SolicitudRegistro(
    canal=Canal.DIME,
    sede="Sede clínica",
    fecha_radicacion=datetime(2026, 10, 30, 16, tzinfo=ZONA_COLOMBIA),
    texto=TEXTO,
    paciente_menor=False,
    peticionario=PETICIONARIO,
)


def _solicitud(**cambios: object) -> SolicitudRegistro:
    return replace(SOLICITUD, **cambios)


class Escenario:
    def __init__(
        self,
        terminos: tuple[Termino, ...],
        festivos: frozenset[date],
        resultado: ResultadoClasificacion = RECLAMO_AUTORIZACION,
    ) -> None:
        self.pqrs = PqrsEnMemoria()
        self.auditoria = AuditoriaEnMemoria()
        self.configuracion = ConfiguracionEnMemoria(terminos, festivos)
        self.cifrador = CifradorAesGcm(LLAVE_CIFRADO, LLAVE_HMAC)
        self.clasificador = ClasificadorFijo(resultado)
        self.caso = RegistrarPqrs(
            pqrs=self.pqrs,
            auditoria=self.auditoria,
            configuracion=self.configuracion,
            cifrador=self.cifrador,
            enmascarador=EnmascaradorReglas(),
            clasificador_provisional=self.clasificador,
            calculadora=CalculadoraDePlazos(),
            semaforo=ReglaSemaforo(0.5),
            reloj=lambda: AHORA,
            id_usuario_actor=1,
            version_instrucciones="clasif-v1.0",
        )


@pytest.fixture
def escenario(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> Escenario:
    return Escenario(terminos, festivos)


def test_registra_con_radicado_estado_y_vencimiento(escenario: Escenario) -> None:
    registrada = escenario.caso.ejecutar(_solicitud())

    vista = registrada.pqrs
    assert (vista.id, vista.radicado) == (1287, "RAD-2026-001287")
    assert (vista.estado, vista.estado_ia) == (EstadoPqrs.REGISTRADA, EstadoIa.PENDIENTE)
    assert vista.fecha_vencimiento == datetime(2026, 11, 2, 16, tzinfo=ZONA_COLOMBIA)
    assert vista.termino.regla == "Reclamo en salud, riesgo simple: 72 horas corridas"
    assert registrada.semaforo.color is Semaforo.VERDE
    assert registrada.semaforo.horas_restantes == 70.0


def test_la_clasificacion_provisional_es_por_reglas_con_nombres(escenario: Escenario) -> None:
    clasificacion = escenario.caso.ejecutar(_solicitud()).pqrs.clasificacion

    assert clasificacion is not None
    assert clasificacion.origen is OrigenClasificacion.REGLAS
    assert clasificacion.area == Referencia(4, "Autorizaciones")
    assert clasificacion.atributo == Referencia(2, "Oportunidad")
    assert (clasificacion.modelo, clasificacion.version_instrucciones) == (None, None)
    [(id_pqrs, guardada)] = escenario.pqrs.clasificaciones
    assert (id_pqrs, guardada.origen, guardada.vigente, guardada.confianza) == (
        1287, OrigenClasificacion.REGLAS, True, 0.5,
    )


def test_el_clasificador_recibe_el_texto_enmascarado_y_el_catalogo(escenario: Escenario) -> None:
    escenario.caso.ejecutar(_solicitud())

    [solicitud] = escenario.clasificador.solicitudes
    assert solicitud.id_pqrs == 1287
    assert solicitud.texto_enmascarado.endswith("Mi teléfono es [TELEFONO_1].")
    assert "3000000000" not in solicitud.texto_enmascarado
    assert solicitud.version_instrucciones == "clasif-v1.0"
    assert {area.nombre for area in solicitud.catalogo.areas} >= {"Autorizaciones"}


def test_guarda_el_texto_enmascarado_y_el_original_cifrado(escenario: Escenario) -> None:
    escenario.caso.ejecutar(_solicitud())

    pqrs = escenario.pqrs.pqrs[1287]
    assert "[TELEFONO_1]" in pqrs.texto_enmascarado
    assert TEXTO.encode() not in pqrs.texto_original_cifrado
    assert escenario.cifrador.descifrar(pqrs.texto_original_cifrado) == TEXTO
    assert (pqrs.canal, pqrs.sede, pqrs.paciente_menor, pqrs.id_termino) == (
        Canal.DIME, "Sede clínica", False, 6,
    )


def test_el_peticionario_queda_con_hmac_y_datos_cifrados(escenario: Escenario) -> None:
    escenario.caso.ejecutar(_solicitud())

    [(huella, (id_peticionario, peticionario))] = escenario.pqrs.peticionarios.items()
    esperado = hmac.new(LLAVE_HMAC, b"CC:1000000001", hashlib.sha256).hexdigest()
    assert huella == peticionario.documento_hash == esperado
    assert escenario.cifrador.descifrar(peticionario.nombre_cifrado) == "Usuario Sintético Uno"
    assert json.loads(escenario.cifrador.descifrar(peticionario.contacto_cifrado)) == {
        "telefono": "3000000000",
        "correo": "usuario1@ejemplo.com",
    }
    assert escenario.pqrs.pqrs[1287].id_peticionario == id_peticionario


def test_el_mismo_documento_reutiliza_al_peticionario(escenario: Escenario) -> None:
    primera = escenario.caso.ejecutar(_solicitud())
    otro_nombre = DatosPeticionario(TipoDocumento.CC, "1000000001", "Otro Nombre Sintético")
    segunda = escenario.caso.ejecutar(_solicitud(peticionario=otro_nombre))

    assert len(escenario.pqrs.peticionarios) == 1
    assert (
        escenario.pqrs.pqrs[primera.pqrs.id].id_peticionario
        == escenario.pqrs.pqrs[segunda.pqrs.id].id_peticionario
    )
    assert segunda.pqrs.radicado == "RAD-2026-001288"


def test_eventos_de_auditoria(escenario: Escenario) -> None:
    escenario.caso.ejecutar(_solicitud())

    eventos = [
        (e.origen, e.accion, e.id_usuario, e.campo, e.valor_anterior, e.valor_nuevo)
        for e in escenario.auditoria.historial(1287)
    ]
    assert eventos == [
        (OrigenEvento.PERSONA, AccionAuditoria.REGISTRAR, 1, "estado", None, "REGISTRADA"),
        (OrigenEvento.SISTEMA, AccionAuditoria.CLASIFICAR_REGLAS, None, "tipo", None, "RECLAMO"),
        (OrigenEvento.SISTEMA, AccionAuditoria.CLASIFICAR_REGLAS, None, "id_atributo", None, "2"),
        (OrigenEvento.SISTEMA, AccionAuditoria.CLASIFICAR_REGLAS, None, "id_area", None, "4"),
        (OrigenEvento.SISTEMA, AccionAuditoria.CLASIFICAR_REGLAS, None, "nivel_riesgo", None, "SIMPLE"),
        (
            OrigenEvento.SISTEMA, AccionAuditoria.CALCULAR_VENCIMIENTO, None, "fecha_vencimiento",
            None, "2026-11-02T16:00:00-05:00",
        ),
    ]
    assert escenario.auditoria.eventos[-1].motivo == "Reclamo en salud, riesgo simple: 72 horas corridas"


def test_ningun_evento_lleva_datos_del_peticionario(escenario: Escenario) -> None:
    escenario.caso.ejecutar(_solicitud())

    texto = repr(escenario.auditoria.eventos)
    for valor in ("1000000001", "Usuario Sintético", "3000000000", "usuario1@"):
        assert valor not in texto


def test_un_reclamo_sin_nivel_queda_simple(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    resultado = ResultadoClasificacion(TipoPqrs.RECLAMO, None, None, NivelRiesgo.NO_APLICA, 0.5)
    escenario = Escenario(terminos, festivos, resultado)

    vista = escenario.caso.ejecutar(_solicitud()).pqrs

    assert vista.nivel_riesgo is NivelRiesgo.SIMPLE
    assert escenario.pqrs.clasificaciones[0][1].nivel_riesgo is NivelRiesgo.SIMPLE
    assert [e.campo for e in escenario.auditoria.eventos if e.accion is AccionAuditoria.CLASIFICAR_REGLAS] == [
        "tipo", "nivel_riesgo",
    ]


def test_menor_de_edad_con_riesgo_vital(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    resultado = ResultadoClasificacion(TipoPqrs.RECLAMO, None, None, NivelRiesgo.VITAL, 0.5)
    escenario = Escenario(terminos, festivos, resultado)

    vista = escenario.caso.ejecutar(_solicitud(paciente_menor=True)).pqrs

    assert vista.fecha_vencimiento == datetime(2026, 10, 31, 0, tzinfo=ZONA_COLOMBIA)
    assert escenario.pqrs.pqrs[vista.id].paciente_menor is True


def test_peticion_en_dias_habiles(terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
    resultado = ResultadoClasificacion(TipoPqrs.PETICION, None, None, NivelRiesgo.NO_APLICA, 0.5)
    escenario = Escenario(terminos, festivos, resultado)

    vista = escenario.caso.ejecutar(_solicitud()).pqrs

    assert vista.fecha_vencimiento == datetime(2026, 11, 24, 23, 59, 59, tzinfo=ZONA_COLOMBIA)
    assert vista.termino.regla == "Petición: 15 días hábiles"
    assert vista.clasificacion is not None and vista.clasificacion.area is None


def test_fecha_futura_es_invalida_y_no_guarda_nada(escenario: Escenario) -> None:
    with pytest.raises(DatosInvalidos) as error:
        escenario.caso.ejecutar(_solicitud(fecha_radicacion=datetime(2026, 10, 30, 18, 0, 1, tzinfo=ZONA_COLOMBIA)))

    assert [e.campo for e in error.value.errores] == ["fecha_radicacion"]
    assert escenario.pqrs.ids_reservados == []
    assert escenario.pqrs.pqrs == {} and escenario.auditoria.eventos == []


def test_la_fecha_igual_al_momento_del_registro_es_valida(escenario: Escenario) -> None:
    assert escenario.caso.ejecutar(_solicitud(fecha_radicacion=AHORA)).pqrs.id == 1287


def test_sin_termino_vigente_falla_sin_guardar(festivos: frozenset[date]) -> None:
    escenario = Escenario((), festivos)

    with pytest.raises(TerminoNoConfigurado):
        escenario.caso.ejecutar(_solicitud())

    assert escenario.pqrs.pqrs == {} and escenario.pqrs.peticionarios == {}
    assert escenario.auditoria.eventos == []


def test_los_terminos_se_piden_para_el_dia_de_radicacion_en_colombia(escenario: Escenario) -> None:
    # 2026-10-30T03:00Z es el 29 de octubre a las 22:00 en Colombia.
    escenario.caso.ejecutar(_solicitud(fecha_radicacion=datetime.fromisoformat("2026-10-30T03:00:00+00:00")))
    assert escenario.configuracion.dias_consultados == [date(2026, 10, 29)]


def test_el_radicado_usa_el_anio_de_colombia() -> None:
    assert formato_radicado(1287, datetime.fromisoformat("2027-01-01T03:00:00+00:00")) == "RAD-2026-001287"
    assert formato_radicado(5, datetime.fromisoformat("2027-01-01T05:00:00+00:00")) == "RAD-2027-000005"
