"""Raíz de composición de Radica.

Es el único módulo que conoce las clases concretas: lee la configuración y
conecta cada puerto con su adaptador (Entrega 2, sección 10.6). Cada solicitud
a la API y cada PQRS que toma el trabajador abren una transacción y reciben
repositorios sobre esa conexión.

Servir la API (desde la raíz del proyecto):
    uvicorn --factory radica.main:crear_aplicacion
Iniciar el trabajador:
    radica-trabajador
"""

import logging
import signal
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from types import FrameType

from fastapi import FastAPI

from radica.adaptadores.entrada.api.app import crear_app
from radica.adaptadores.entrada.api.casos import CasosDeUso
from radica.adaptadores.entrada.trabajador.bucle import INTERVALO_S, Trabajador
from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.adaptadores.salida.ia.claude import AdaptadorClaude
from radica.adaptadores.salida.ia.respaldo import ClasificadorConRespaldo
from radica.adaptadores.salida.palabras_clave.clasificador import ClasificadorPalabrasClave
from radica.adaptadores.salida.postgres.repositorios import (
    AuditoriaRepositoryPostgres,
    ConfiguracionRepositoryPostgres,
    PqrsRepositoryPostgres,
    comprobar_conexion,
    crear_motor,
)
from radica.aplicacion.casos_de_uso.consultas import (
    ConsultarHistorial,
    ConsultarPqrs,
    ListarBandeja,
    ListarTerminos,
)
from radica.aplicacion.casos_de_uso.clasificar_pqrs import ClasificarPqrs
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs
from radica.aplicacion.casos_de_uso.solicitar_clasificacion import SolicitarClasificacion
from radica.aplicacion.puertos.clasificador import ClasificadorPqrs
from radica.config import PROVEEDOR_CLAUDE, Configuracion, cargar
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos
from radica.dominio.riesgo import PoliticaDeRiesgo
from radica.dominio.semaforo import ReglaSemaforo

VERSION_INSTRUCCIONES = "clasif-v1.0"
ID_USUARIO_ACTOR = 1  # «Funcionario Sintético»: sin autenticación en esta entrega (contexto.md 4.12)
SEGUN_CONFIGURACION = object()  # componer_trabajador: usar el clasificador que diga IA_PROVIDER


def ahora_en_colombia() -> datetime:
    return datetime.now(ZONA_COLOMBIA)


def construir_clasificador_ia(configuracion: Configuracion) -> ClasificadorPqrs | None:
    """IA_PROVIDER=claude: Claude y, si falla, palabras clave (10.4). ninguno: None, sin proveedor (4.9)."""
    if configuracion.ia_proveedor != PROVEEDOR_CLAUDE:
        return None
    assert configuracion.ia_api_key is not None  # config.leer() la exige con claude
    principal = AdaptadorClaude.con_clave(
        api_key=configuracion.ia_api_key,
        modelo=configuracion.ia_modelo,
        timeout_s=configuracion.ia_timeout_s,
        precio_entrada_usd_mtok=configuracion.precio_entrada_usd_mtok,
        precio_salida_usd_mtok=configuracion.precio_salida_usd_mtok,
    )
    return ClasificadorConRespaldo([principal, ClasificadorPalabrasClave()])


def componer(
    configuracion: Configuracion,
    reloj: Callable[[], datetime] = ahora_en_colombia,
    clasificador_provisional: ClasificadorPqrs | None = None,
    id_usuario_actor: int = ID_USUARIO_ACTOR,
) -> FastAPI:
    """Arma la API con la configuración dada; las pruebas pasan su base, sus llaves y su reloj."""
    motor = crear_motor(configuracion.url_base_datos)
    cifrador = CifradorAesGcm(configuracion.llave_cifrado, configuracion.llave_hmac)
    enmascarador = EnmascaradorReglas()
    clasificador = clasificador_provisional or ClasificadorPalabrasClave()
    calculadora = CalculadoraDePlazos()
    semaforo = ReglaSemaforo(configuracion.umbral_amarillo)

    @contextmanager
    def casos() -> Iterator[CasosDeUso]:
        with motor.begin() as conexion:
            pqrs = PqrsRepositoryPostgres(conexion)
            auditoria = AuditoriaRepositoryPostgres(conexion)
            terminos = ConfiguracionRepositoryPostgres(conexion)
            yield CasosDeUso(
                registrar=RegistrarPqrs(
                    pqrs=pqrs,
                    auditoria=auditoria,
                    configuracion=terminos,
                    cifrador=cifrador,
                    enmascarador=enmascarador,
                    clasificador_provisional=clasificador,
                    calculadora=calculadora,
                    semaforo=semaforo,
                    reloj=reloj,
                    id_usuario_actor=id_usuario_actor,
                    version_instrucciones=VERSION_INSTRUCCIONES,
                ),
                consultar=ConsultarPqrs(pqrs, semaforo, reloj),
                bandeja=ListarBandeja(pqrs, semaforo, reloj),
                historial=ConsultarHistorial(pqrs, auditoria),
                terminos=ListarTerminos(terminos, reloj),
                solicitar_clasificacion=SolicitarClasificacion(pqrs, auditoria, id_usuario_actor),
            )

    return crear_app(casos, lambda: comprobar_conexion(motor))


def crear_aplicacion() -> FastAPI:
    """Punto de entrada de uvicorn. No arranca si falta una variable obligatoria."""
    return componer(cargar())


def componer_trabajador(
    configuracion: Configuracion,
    clasificador_ia: ClasificadorPqrs | None | object = SEGUN_CONFIGURACION,
    intervalo_s: float = INTERVALO_S,
) -> Trabajador:
    """Arma el trabajador; las pruebas pasan su base y un clasificador falso, sin red."""
    motor = crear_motor(configuracion.url_base_datos)
    cifrador = CifradorAesGcm(configuracion.llave_cifrado, configuracion.llave_hmac)
    enmascarador = EnmascaradorReglas()
    clasificador = (
        construir_clasificador_ia(configuracion)
        if clasificador_ia is SEGUN_CONFIGURACION
        else clasificador_ia
    )
    calculadora = CalculadoraDePlazos()
    politica = PoliticaDeRiesgo(configuracion.umbral_confianza)

    @contextmanager
    def unidad() -> Iterator[ClasificarPqrs]:
        with motor.begin() as conexion:
            yield ClasificarPqrs(
                pqrs=PqrsRepositoryPostgres(conexion),
                auditoria=AuditoriaRepositoryPostgres(conexion),
                configuracion=ConfiguracionRepositoryPostgres(conexion),
                cifrador=cifrador,
                enmascarador=enmascarador,
                clasificador=clasificador,  # type: ignore[arg-type]
                calculadora=calculadora,
                politica=politica,
                version_instrucciones=VERSION_INSTRUCCIONES,
            )

    return Trabajador(unidad, intervalo_s)


def ejecutar_trabajador() -> None:
    """Comando radica-trabajador. Se detiene con Ctrl+C o con SIGTERM (docker compose stop)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    configuracion = cargar()
    trabajador = componer_trabajador(configuracion)
    logging.getLogger("radica.trabajador").info("Proveedor de IA: %s", configuracion.ia_proveedor)

    def detener(_senal: int, _marco: FrameType | None) -> None:
        trabajador.detener()

    signal.signal(signal.SIGTERM, detener)
    signal.signal(signal.SIGINT, detener)
    trabajador.ejecutar()
