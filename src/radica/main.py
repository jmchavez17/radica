"""Raíz de composición de Radica.

Es el único módulo que conoce las clases concretas: lee la configuración y
conecta cada puerto con su adaptador (Entrega 2, sección 10.6). Cada solicitud
a la API abre una transacción y recibe repositorios sobre esa conexión.

Servir la API (desde la raíz del proyecto):
    uvicorn --factory radica.main:crear_aplicacion
"""

import re
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI

from radica.adaptadores.entrada.api.app import crear_app
from radica.adaptadores.entrada.api.casos import CasosDeUso
from radica.adaptadores.salida.cifrado.aes_gcm import CifradorAesGcm
from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
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
from radica.aplicacion.puertos.clasificador import (
    ClasificadorPqrs,
    ResultadoClasificacion,
    SolicitudClasificacion,
)
from radica.config import Configuracion, cargar
from radica.dominio.plazos import ZONA_COLOMBIA, CalculadoraDePlazos
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import NivelRiesgo, TipoPqrs

VERSION_INSTRUCCIONES = "clasif-v1.0"
ID_USUARIO_ACTOR = 1  # «Funcionario Sintético»: sin autenticación en esta entrega (contexto.md 4.12)


class ClasificadorProvisionalMinimo:
    """TEMPORAL (contexto.md 4.5): unas pocas palabras mientras entra la rama de Isabella.

    Lo reemplaza ClasificadorPalabrasClave, con su diccionario versionado.
    """

    # (patrón sobre el texto sin tildes y en minúsculas, tipo, nivel, id_area)
    REGLAS = (
        (r"\briesgo vital\b", TipoPqrs.RECLAMO, NivelRiesgo.VITAL, None),
        (r"\bautorizacion(es)?\b", TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 4),
        (r"\bcitas?\b", TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 2),
        (r"\bmedicamentos?\b", TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 6),
        (r"\btrato\b|\bgroser[oa]s?\b", TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA, None),
    )

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        texto = "".join(
            letra
            for letra in unicodedata.normalize("NFKD", solicitud.texto_enmascarado.casefold())
            if not unicodedata.combining(letra)
        )
        for patron, tipo, nivel, id_area in self.REGLAS:
            encontrado = re.search(patron, texto)
            if encontrado:
                senales = (encontrado.group(),) if nivel is NivelRiesgo.VITAL else ()
                return ResultadoClasificacion(
                    tipo, None, id_area, nivel, confianza=0.5, senales_riesgo=senales
                )
        return ResultadoClasificacion(TipoPqrs.PETICION, None, None, NivelRiesgo.NO_APLICA, 0.5)


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
    clasificador = clasificador_provisional or ClasificadorProvisionalMinimo()
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
