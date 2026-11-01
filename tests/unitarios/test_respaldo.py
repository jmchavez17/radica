"""ClasificadorConRespaldo (Entrega 2, 10.4) y la selección por IA_PROVIDER en main.py."""

import os
from dataclasses import replace
from decimal import Decimal

import anthropic
import httpx2
import pytest
from dobles import CATALOGO, ClasificadorFijo, ClasificadorQueFalla, ClienteClaudeFalso, mensaje_claude

from radica.adaptadores.salida.ia.claude import AdaptadorClaude
from radica.adaptadores.salida.ia.respaldo import ClasificadorConRespaldo
from radica.adaptadores.salida.palabras_clave.clasificador import ClasificadorPalabrasClave
from radica.aplicacion.puertos.clasificador import (
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    SolicitudClasificacion,
    UsoIA,
)
from radica.config import Configuracion
from radica.dominio.valores import NivelRiesgo, ResultadoLlamadaIA, TipoPqrs
from radica.main import construir_clasificador_ia

SOLICITUD = SolicitudClasificacion(
    7, "Mi papá tiene dificultad para respirar y no le dan la cita. [TELEFONO_1]", CATALOGO, "clasif-v1.0"
)
QUEJA = ResultadoClasificacion(TipoPqrs.QUEJA, None, 1, NivelRiesgo.NO_APLICA, 0.5)


def _uso(intento: int, resultado: ResultadoLlamadaIA) -> UsoIA:
    return UsoIA("anthropic", "claude-haiku-5-5", 0, 0, Decimal(0), 15000, intento, resultado)


def test_si_el_primero_responde_no_se_llama_al_respaldo() -> None:
    principal, respaldo = ClasificadorFijo(QUEJA), ClasificadorFijo(QUEJA)

    assert ClasificadorConRespaldo([principal, respaldo]).clasificar(SOLICITUD) == QUEJA
    assert len(principal.solicitudes) == 1 and respaldo.solicitudes == []


@pytest.mark.parametrize("error", [ProveedorNoDisponible, SalidaInvalida])
def test_si_el_primero_falla_responde_el_siguiente_con_los_intentos_acumulados(
    error: type[ProveedorNoDisponible | SalidaInvalida],
) -> None:
    intentos = (_uso(1, ResultadoLlamadaIA.TIMEOUT), _uso(2, ResultadoLlamadaIA.TIMEOUT))
    propios = (_uso(1, ResultadoLlamadaIA.LIMITE_CUOTA),)
    respaldo = ClasificadorFijo(replace(QUEJA, intentos_fallidos=propios))

    resultado = ClasificadorConRespaldo([ClasificadorQueFalla(error("falló", intentos)), respaldo]).clasificar(
        SOLICITUD
    )

    assert (resultado.tipo, resultado.uso) == (TipoPqrs.QUEJA, None)
    assert resultado.intentos_fallidos == intentos + propios
    assert respaldo.solicitudes == [SOLICITUD]


def test_si_fallan_todos_lanza_el_ultimo_error_con_todos_los_intentos() -> None:
    primero = ProveedorNoDisponible("sin red", (_uso(1, ResultadoLlamadaIA.ERROR_PROVEEDOR),))
    segundo = SalidaInvalida("fuera del catálogo", (_uso(1, ResultadoLlamadaIA.SALIDA_INVALIDA),))

    with pytest.raises(SalidaInvalida, match="fuera del catálogo") as capturado:
        ClasificadorConRespaldo([ClasificadorQueFalla(primero), ClasificadorQueFalla(segundo)]).clasificar(
            SOLICITUD
        )

    assert [u.resultado for u in capturado.value.intentos] == [
        ResultadoLlamadaIA.ERROR_PROVEEDOR, ResultadoLlamadaIA.SALIDA_INVALIDA,
    ]


def test_un_error_que_no_es_del_puerto_no_se_esconde() -> None:
    with pytest.raises(RuntimeError):
        ClasificadorConRespaldo([ClasificadorQueFalla(RuntimeError("defecto")), ClasificadorFijo(QUEJA)]).clasificar(
            SOLICITUD
        )


def test_necesita_al_menos_un_clasificador() -> None:
    with pytest.raises(ValueError, match="al menos un clasificador"):
        ClasificadorConRespaldo([])


def test_claude_caido_cae_en_las_palabras_clave_reales() -> None:
    caido = httpx2.Response(503, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    error = anthropic.ServiceUnavailableError("no disponible", response=caido, body=None)
    claude = AdaptadorClaude(
        ClienteClaudeFalso(error, error, error), "claude-haiku-5-5", Decimal("0.10"), Decimal("0.50"),
        esperar=lambda _: None,
    )

    resultado = ClasificadorConRespaldo([claude, ClasificadorPalabrasClave()]).clasificar(SOLICITUD)

    assert (resultado.tipo, resultado.nivel_riesgo, resultado.confianza) == (
        TipoPqrs.RECLAMO, NivelRiesgo.VITAL, 0.5,
    )
    assert resultado.uso is None
    assert [u.intento for u in resultado.intentos_fallidos] == [1, 2, 3]


# --- Selección por IA_PROVIDER (contexto.md 4.9 y 10.6) ---

def _configuracion(**cambios: object) -> Configuracion:
    base = Configuracion("postgresql+psycopg://x@127.0.0.1:5433/x", os.urandom(32), os.urandom(32))
    return replace(base, **cambios)


def test_con_ninguno_no_hay_clasificador_de_ia() -> None:
    assert construir_clasificador_ia(_configuracion(ia_proveedor="ninguno")) is None


def test_con_claude_la_cadena_es_claude_y_despues_palabras_clave() -> None:
    clasificador = construir_clasificador_ia(
        _configuracion(ia_proveedor="claude", ia_api_key="clave-falsa-de-prueba", ia_timeout_s=12.0)
    )

    assert isinstance(clasificador, ClasificadorConRespaldo)
    principal, respaldo = clasificador.clasificadores
    assert isinstance(principal, AdaptadorClaude) and isinstance(respaldo, ClasificadorPalabrasClave)
    assert principal._cliente.timeout == 12.0  # noqa: SLF001


def test_la_cadena_de_claude_responde_con_el_cliente_falso() -> None:
    claude = AdaptadorClaude(ClienteClaudeFalso(mensaje_claude()), "claude-haiku-5-5", Decimal("0.10"), Decimal("0.50"))

    resultado = ClasificadorConRespaldo([claude, ClasificadorPalabrasClave()]).clasificar(SOLICITUD)

    assert resultado.uso is not None and resultado.uso.resultado is ResultadoLlamadaIA.OK
