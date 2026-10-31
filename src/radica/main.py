"""Raíz de composición de Radica.

Es el único módulo que conoce las clases concretas: lee la configuración y
conecta cada puerto con su adaptador (Entrega 2, sección 10.6). Cada solicitud
a la API abre una transacción y recibe repositorios sobre esa conexión.

Servir la API (desde la raíz del proyecto):
    uvicorn --factory radica.main:crear_aplicacion
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI

from radica.adaptadores.entrada.api.app import crear_app
from radica.adaptadores.entrada.api.casos import CasosDeUso
from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
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
from radica.aplicacion.casos_de_uso.registrar_pqrs import RegistrarPqrs
from radica.aplicacion.puertos.clasificador import ClasificadorPqrs
from radica.config import Configuracion, cargar
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos
from radica.dominio.semaforo import ReglaSemaforo

VERSION_INSTRUCCIONES = "clasif-v1.0"
ID_USUARIO_ACTOR = 1  # «Funcionario Sintético»: sin autenticación en esta entrega (contexto.md 4.12)


def ahora_en_colombia() -> datetime:
    return datetime.now(ZONA_COLOMBIA)


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
            )

    return crear_app(casos, lambda: comprobar_conexion(motor))


def crear_aplicacion() -> FastAPI:
    """Punto de entrada de uvicorn. No arranca si falta una variable obligatoria."""
    return componer(cargar())
