"""Caso de uso RegistrarPqrs (HU-01; contexto.md 4.1 a 4.8 y 4.12).

Todo ocurre dentro de la transacción que abre quien lo invoca: si un paso
falla no queda nada guardado. No espera a la IA: la deja en PENDIENTE para el
trabajador (RNF-10). El clasificador que recibe es el provisional por reglas.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from radica.aplicacion.casos_de_uso.errores import DatosInvalidos, ErrorDeCampo
from radica.aplicacion.casos_de_uso.resultados import PqrsConSemaforo
from radica.aplicacion.puertos.auditoria import AuditoriaRepository
from radica.aplicacion.puertos.cifrador import Cifrador
from radica.aplicacion.puertos.clasificador import Catalogo, ClasificadorPqrs, SolicitudClasificacion
from radica.aplicacion.puertos.configuracion import ConfiguracionRepository
from radica.aplicacion.puertos.enmascarador import Enmascarador
from radica.aplicacion.puertos.pqrs import ClasificacionVigente, PqrsRepository, VistaPqrs
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import (
    CalculadoraDePlazos,
    dia_en_colombia,
    nivel_efectivo,
    seleccionar_termino,
)
from radica.dominio.pqrs import (
    Clasificacion,
    EventoAuditoria,
    PeticionarioCifrado,
    Pqrs,
    Referencia,
    formato_radicado,
)
from radica.dominio.semaforo import ReglaSemaforo
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    OrigenClasificacion,
    OrigenEvento,
)

MOTIVO_REGLAS = "Clasificación provisional por reglas"


@dataclass(frozen=True)
class SolicitudRegistro:
    canal: Canal
    sede: str | None
    fecha_radicacion: datetime
    texto: str = field(repr=False)
    paciente_menor: bool
    peticionario: DatosPeticionario


class RegistrarPqrs:
    def __init__(
        self,
        pqrs: PqrsRepository,
        auditoria: AuditoriaRepository,
        configuracion: ConfiguracionRepository,
        cifrador: Cifrador,
        enmascarador: Enmascarador,
        clasificador_provisional: ClasificadorPqrs,
        calculadora: CalculadoraDePlazos,
        semaforo: ReglaSemaforo,
        reloj: Callable[[], datetime],
        id_usuario_actor: int,
        version_instrucciones: str,
    ) -> None:
        self._pqrs = pqrs
        self._auditoria = auditoria
        self._configuracion = configuracion
        self._cifrador = cifrador
        self._enmascarador = enmascarador
        self._clasificador = clasificador_provisional
        self._calculadora = calculadora
        self._semaforo = semaforo
        self._reloj = reloj
        self._id_usuario = id_usuario_actor
        self._version = version_instrucciones

    def ejecutar(self, solicitud: SolicitudRegistro) -> PqrsConSemaforo:
        ahora = self._reloj()
        fecha = solicitud.fecha_radicacion
        if fecha > ahora:
            raise DatosInvalidos(
                [ErrorDeCampo("fecha_radicacion", "No puede ser posterior al momento del registro.")]
            )

        id_pqrs = self._pqrs.reservar_id()
        enmascarado = self._enmascarador.enmascarar(solicitud.texto, solicitud.peticionario)
        catalogo = self._configuracion.catalogo()
        resultado = self._clasificador.clasificar(
            SolicitudClasificacion(id_pqrs, enmascarado.texto, catalogo, self._version)
        )
        nivel = nivel_efectivo(resultado.tipo, resultado.nivel_riesgo)

        termino = seleccionar_termino(
            self._configuracion.terminos_vigentes(dia_en_colombia(fecha)),
            resultado.tipo,
            nivel,
            solicitud.paciente_menor,
            fecha,
        )
        festivos = (
            self._configuracion.festivos(termino.id_calendario)
            if termino.id_calendario is not None
            else frozenset()
        )
        vencimiento = self._calculadora.calcular(termino, fecha, festivos)

        id_peticionario = self._pqrs.obtener_o_crear_peticionario(
            self._cifrar_peticionario(solicitud.peticionario)
        )
        pqrs = Pqrs(
            id=id_pqrs,
            radicado=formato_radicado(id_pqrs, fecha),
            id_peticionario=id_peticionario,
            canal=solicitud.canal,
            sede=solicitud.sede,
            fecha_radicacion=fecha,
            texto_original_cifrado=self._cifrador.cifrar(solicitud.texto),
            texto_enmascarado=enmascarado.texto,
            tipo=resultado.tipo,
            id_atributo=resultado.id_atributo,
            nivel_riesgo=nivel,
            paciente_menor=solicitud.paciente_menor,
            id_termino=termino.id,
            fecha_vencimiento=vencimiento,
            estado=EstadoPqrs.REGISTRADA,
            estado_ia=EstadoIa.PENDIENTE,
        )
        self._pqrs.guardar(pqrs)
        clasificacion = Clasificacion(
            origen=OrigenClasificacion.REGLAS,
            tipo=resultado.tipo,
            id_atributo=resultado.id_atributo,
            id_area=resultado.id_area,
            nivel_riesgo=nivel,
            confianza=resultado.confianza,
            resumen=resultado.resumen,
            datos_extraidos=dict(resultado.datos_clave) or None,
        )
        self._pqrs.guardar_clasificacion(id_pqrs, clasificacion)
        for evento in self._eventos(pqrs, clasificacion, termino.regla):
            self._auditoria.registrar(evento)

        vista = VistaPqrs(
            id=pqrs.id,
            radicado=pqrs.radicado,
            canal=pqrs.canal,
            sede=pqrs.sede,
            fecha_radicacion=fecha,
            texto_enmascarado=pqrs.texto_enmascarado,
            tipo=pqrs.tipo,
            nivel_riesgo=pqrs.nivel_riesgo,
            estado=pqrs.estado,
            estado_ia=pqrs.estado_ia,
            fecha_vencimiento=vencimiento,
            termino=termino,
            clasificacion=_vigente(clasificacion, catalogo),
        )
        return PqrsConSemaforo(vista, self._semaforo.evaluar(fecha, vencimiento, ahora))

    def _cifrar_peticionario(self, datos: DatosPeticionario) -> PeticionarioCifrado:
        contacto = json.dumps(
            {"telefono": datos.telefono, "correo": datos.correo}, ensure_ascii=False
        )
        return PeticionarioCifrado(
            documento_hash=self._cifrador.huella(
                f"{datos.tipo_documento.value}:{datos.numero_documento}"
            ),
            nombre_cifrado=self._cifrador.cifrar(datos.nombre),
            contacto_cifrado=self._cifrador.cifrar(contacto),
        )

    def _eventos(self, pqrs: Pqrs, clasificacion: Clasificacion, regla: str) -> list[EventoAuditoria]:
        eventos = [
            EventoAuditoria(
                pqrs.id,
                OrigenEvento.PERSONA,
                AccionAuditoria.REGISTRAR,
                id_usuario=self._id_usuario,
                campo="estado",
                valor_nuevo=pqrs.estado.value,
            )
        ]
        campos = {
            "tipo": clasificacion.tipo.value,
            "id_atributo": clasificacion.id_atributo,
            "id_area": clasificacion.id_area,
            "nivel_riesgo": clasificacion.nivel_riesgo.value,
        }
        eventos += [
            EventoAuditoria(
                pqrs.id,
                OrigenEvento.SISTEMA,
                AccionAuditoria.CLASIFICAR_REGLAS,
                campo=campo,
                valor_nuevo=str(valor),
                motivo=MOTIVO_REGLAS,
            )
            for campo, valor in campos.items()
            if valor is not None
        ]
        eventos.append(
            EventoAuditoria(
                pqrs.id,
                OrigenEvento.SISTEMA,
                AccionAuditoria.CALCULAR_VENCIMIENTO,
                campo="fecha_vencimiento",
                valor_nuevo=pqrs.fecha_vencimiento.isoformat(),
                motivo=regla,
            )
        )
        return eventos


def _vigente(clasificacion: Clasificacion, catalogo: Catalogo) -> ClasificacionVigente:
    atributos = {atributo.id: atributo.nombre for atributo in catalogo.atributos}
    areas = {area.id: area.nombre for area in catalogo.areas}

    def referencia(id_: int | None, nombres: dict[int, str]) -> Referencia | None:
        return Referencia(id_, nombres[id_]) if id_ is not None and id_ in nombres else None

    return ClasificacionVigente(
        origen=clasificacion.origen,
        tipo=clasificacion.tipo,
        atributo=referencia(clasificacion.id_atributo, atributos),
        area=referencia(clasificacion.id_area, areas),
        nivel_riesgo=clasificacion.nivel_riesgo,
        confianza=clasificacion.confianza,
        resumen=clasificacion.resumen,
    )
