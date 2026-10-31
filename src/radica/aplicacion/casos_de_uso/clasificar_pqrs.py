"""Caso de uso ClasificarPqrs (HU-03, HU-04 y HU-05; contexto.md 4.4, 4.9 y 4.12; ADR-03).

En este orden: verifica el enmascaramiento, arma la SolicitudClasificacion con
el catálogo de la base, llama al puerto ClasificadorPqrs, aplica la
PoliticaDeRiesgo y guarda. Si la verificación falla no hay ninguna llamada
(falla cerrada). Todo ocurre dentro de la transacción que abre quien lo
invoca; el trabajador la mantiene mientras la PQRS está bloqueada.
"""

import json
from dataclasses import dataclass

from radica.aplicacion.casos_de_uso.errores import PqrsNoEncontrada
from radica.aplicacion.puertos.auditoria import AuditoriaRepository
from radica.aplicacion.puertos.cifrador import Cifrador
from radica.aplicacion.puertos.clasificador import (
    ClasificadorPqrs,
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    SolicitudClasificacion,
    UsoIA,
)
from radica.aplicacion.puertos.configuracion import ConfiguracionRepository
from radica.aplicacion.puertos.enmascarador import Enmascarador
from radica.aplicacion.puertos.pqrs import PqrsParaClasificar, PqrsRepository
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.plazos import CalculadoraDePlazos, dia_en_colombia, nivel_efectivo, seleccionar_termino
from radica.dominio.pqrs import Clasificacion, EventoAuditoria, PeticionarioCifrado
from radica.dominio.riesgo import ClasificacionConPlazo, PoliticaDeRiesgo
from radica.dominio.valores import (
    AccionAuditoria,
    EstadoIa,
    EstadoPqrs,
    OrigenClasificacion,
    OrigenEvento,
    TipoDocumento,
)

MOTIVO_IA_DESACTIVADA = "IA desactivada por configuración"
MAXIMO_MOTIVO = 300  # auditoria.motivo es VARCHAR(300)


def _recortar(texto: str) -> str:
    return texto if len(texto) <= MAXIMO_MOTIVO else texto[: MAXIMO_MOTIVO - 1] + "…"


def _confianza(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


@dataclass(frozen=True)
class _Cambio:
    campo: str
    anterior: object
    nuevo: object


class ClasificarPqrs:
    """clasificador None significa IA_PROVIDER=ninguno: no se llama a ningún proveedor."""

    def __init__(
        self,
        pqrs: PqrsRepository,
        auditoria: AuditoriaRepository,
        configuracion: ConfiguracionRepository,
        cifrador: Cifrador,
        enmascarador: Enmascarador,
        clasificador: ClasificadorPqrs | None,
        calculadora: CalculadoraDePlazos,
        politica: PoliticaDeRiesgo,
        version_instrucciones: str,
    ) -> None:
        self._pqrs = pqrs
        self._auditoria = auditoria
        self._configuracion = configuracion
        self._cifrador = cifrador
        self._enmascarador = enmascarador
        self._clasificador = clasificador
        self._calculadora = calculadora
        self._politica = politica
        self._version = version_instrucciones

    def tomar_siguiente(self) -> int | None:
        """La PQRS pendiente más antigua que nadie tenga bloqueada, ya bloqueada; None si no hay."""
        pendientes = self._pqrs.pendientes_de_ia(1)
        return pendientes[0] if pendientes else None

    def registrar_error_interno(self, id_pqrs: int) -> None:
        """Para el trabajador, en una transacción nueva después de un error inesperado.

        Sin esto la PQRS seguiría PENDIENTE y se volvería a tomar (y a pagar) sin fin.
        """
        datos = self._pqrs.obtener_para_clasificar(id_pqrs)
        if datos is None or datos.estado_ia is not EstadoIa.PENDIENTE:
            return
        self._sin_ia(
            datos,
            EstadoIa.FALLIDA,
            AccionAuditoria.IA_FALLIDA,
            "Error interno al clasificar. Sigue vigente la clasificación por reglas.",
        )

    def ejecutar(self, id_pqrs: int) -> EstadoIa:
        datos = self._pqrs.obtener_para_clasificar(id_pqrs)
        if datos is None:
            raise PqrsNoEncontrada(id_pqrs)
        if datos.estado_ia is not EstadoIa.PENDIENTE:
            return datos.estado_ia

        verificacion = self._enmascarador.verificar(
            datos.texto_enmascarado, self._datos_peticionario(datos.peticionario)
        )
        if not verificacion.limpio:
            tipos = ", ".join(verificacion.tipos_detectados)
            return self._sin_ia(
                datos,
                EstadoIa.OMITIDA,
                AccionAuditoria.IA_OMITIDA,
                f"Enmascaramiento no verificado: quedan datos de tipo {tipos}. No se llamó a la IA.",
            )
        if self._clasificador is None:
            return self._sin_ia(
                datos, EstadoIa.OMITIDA, AccionAuditoria.IA_OMITIDA, MOTIVO_IA_DESACTIVADA
            )

        solicitud = SolicitudClasificacion(
            datos.id, datos.texto_enmascarado, self._configuracion.catalogo(), self._version
        )
        try:
            resultado = self._clasificador.clasificar(solicitud)
        except (ProveedorNoDisponible, SalidaInvalida) as error:
            self._registrar_llamadas(datos.id, error.intentos)
            return self._fallida(datos, error.intentos)

        if resultado.uso is None:
            # Respondió un clasificador local: el proveedor falló y quedó el respaldo (4.9).
            self._registrar_llamadas(datos.id, resultado.intentos_fallidos)
            return self._fallida(datos, resultado.intentos_fallidos)

        self._registrar_llamadas(datos.id, resultado.intentos_fallidos)
        id_llamada = self._auditoria.registrar_llamada_ia(datos.id, resultado.uso, self._version)
        self._aplicar_politica(datos, resultado, id_llamada)
        return EstadoIa.COMPLETADA

    def _datos_peticionario(self, cifrado: PeticionarioCifrado) -> DatosPeticionario:
        """El documento solo existe como HMAC (decisión D4): los detectores buscan las cédulas.

        tipo_documento no interviene en el enmascaramiento.
        """
        contacto = json.loads(self._cifrador.descifrar(cifrado.contacto_cifrado))
        return DatosPeticionario(
            tipo_documento=TipoDocumento.CC,
            numero_documento="",
            nombre=self._cifrador.descifrar(cifrado.nombre_cifrado),
            telefono=contacto.get("telefono"),
            correo=contacto.get("correo"),
        )

    def _registrar_llamadas(self, id_pqrs: int, intentos: tuple[UsoIA, ...]) -> None:
        for uso in intentos:
            self._auditoria.registrar_llamada_ia(id_pqrs, uso, self._version)

    def _fallida(self, datos: PqrsParaClasificar, intentos: tuple[UsoIA, ...]) -> EstadoIa:
        detalle = f" ({intentos[-1].resultado.value})" if intentos else ""
        return self._sin_ia(
            datos,
            EstadoIa.FALLIDA,
            AccionAuditoria.IA_FALLIDA,
            f"El proveedor de IA no dio una clasificación válida{detalle}."
            " Sigue vigente la clasificación por reglas.",
        )

    def _sin_ia(
        self, datos: PqrsParaClasificar, estado_ia: EstadoIa, accion: AccionAuditoria, motivo: str
    ) -> EstadoIa:
        """OMITIDA o FALLIDA: la clasificación por reglas sigue vigente y la PQRS pide revisión."""
        self._pqrs.actualizar_estado(datos.id, EstadoPqrs.REQUIERE_REVISION, estado_ia)
        self._auditoria.registrar(
            EventoAuditoria(
                datos.id,
                OrigenEvento.SISTEMA,
                accion,
                campo="estado_ia",
                valor_anterior=datos.estado_ia.value,
                valor_nuevo=estado_ia.value,
                motivo=_recortar(motivo),
            )
        )
        return estado_ia

    def _aplicar_politica(
        self, datos: PqrsParaClasificar, resultado: ResultadoClasificacion, id_llamada: int
    ) -> None:
        nivel = nivel_efectivo(resultado.tipo, resultado.nivel_riesgo)
        termino = seleccionar_termino(
            self._configuracion.terminos_vigentes(dia_en_colombia(datos.fecha_radicacion)),
            resultado.tipo,
            nivel,
            datos.paciente_menor,
            datos.fecha_radicacion,
        )
        festivos = (
            self._configuracion.festivos(termino.id_calendario)
            if termino.id_calendario is not None
            else frozenset()
        )
        vencimiento = self._calculadora.calcular(termino, datos.fecha_radicacion, festivos)
        decision = self._politica.decidir(
            ClasificacionConPlazo(datos.tipo, datos.nivel_riesgo, datos.fecha_vencimiento),
            ClasificacionConPlazo(resultado.tipo, nivel, vencimiento),
            resultado.confianza,
        )
        clasificacion = Clasificacion(
            origen=OrigenClasificacion.IA,
            tipo=resultado.tipo,
            id_atributo=resultado.id_atributo,
            id_area=resultado.id_area,
            nivel_riesgo=nivel,
            confianza=resultado.confianza,
            resumen=resultado.resumen,
            datos_extraidos=dict(resultado.datos_clave) or None,
            id_llamada_ia=id_llamada,
            vigente=decision.aplicar,
        )

        if not decision.aplicar:
            self._pqrs.guardar_clasificacion(datos.id, clasificacion)
            self._pqrs.actualizar_estado(datos.id, EstadoPqrs.REQUIERE_REVISION, EstadoIa.COMPLETADA)
            self._auditoria.registrar(
                EventoAuditoria(
                    datos.id,
                    OrigenEvento.SISTEMA,
                    AccionAuditoria.SUGERENCIA_IA_NO_APLICADA,
                    campo="estado",
                    valor_anterior=datos.estado.value,
                    valor_nuevo=EstadoPqrs.REQUIERE_REVISION.value,
                    motivo=_recortar(
                        f"{decision.motivo} Sugería {resultado.tipo.value} con riesgo {nivel.value}"
                        f" (confianza {_confianza(resultado.confianza)})."
                    ),
                )
            )
            return

        self._pqrs.retirar_clasificacion_vigente(datos.id)
        self._pqrs.guardar_clasificacion(datos.id, clasificacion)
        self._pqrs.actualizar_clasificacion(
            datos.id, resultado.tipo, resultado.id_atributo, nivel, termino.id, vencimiento
        )
        self._pqrs.actualizar_estado(datos.id, decision.estado, EstadoIa.COMPLETADA)

        aplicada = f"Sugerencia de la IA aplicada (confianza {_confianza(resultado.confianza)})."
        cambios = [
            _Cambio("tipo", datos.tipo.value, resultado.tipo.value),
            _Cambio("id_atributo", datos.id_atributo, resultado.id_atributo),
            _Cambio("id_area", datos.id_area, resultado.id_area),
            _Cambio("nivel_riesgo", datos.nivel_riesgo.value, nivel.value),
            _Cambio("estado", datos.estado.value, decision.estado.value),
        ]
        for cambio in cambios:
            if cambio.anterior == cambio.nuevo:
                continue
            motivo = aplicada
            if cambio.campo == "nivel_riesgo" and resultado.senales_riesgo:
                motivo += " Señales de riesgo: " + "; ".join(resultado.senales_riesgo) + "."
            if cambio.campo == "estado" and decision.motivo:
                motivo = decision.motivo
            self._auditoria.registrar(
                EventoAuditoria(
                    datos.id,
                    OrigenEvento.IA,
                    AccionAuditoria.CLASIFICAR_IA,
                    campo=cambio.campo,
                    valor_anterior=None if cambio.anterior is None else str(cambio.anterior),
                    valor_nuevo=None if cambio.nuevo is None else str(cambio.nuevo),
                    motivo=_recortar(motivo),
                )
            )
        if vencimiento != datos.fecha_vencimiento:
            self._auditoria.registrar(
                EventoAuditoria(
                    datos.id,
                    OrigenEvento.SISTEMA,
                    AccionAuditoria.CALCULAR_VENCIMIENTO,
                    campo="fecha_vencimiento",
                    valor_anterior=datos.fecha_vencimiento.isoformat(),
                    valor_nuevo=vencimiento.isoformat(),
                    motivo=termino.regla,
                )
            )
