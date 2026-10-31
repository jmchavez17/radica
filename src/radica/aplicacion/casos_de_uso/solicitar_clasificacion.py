"""Caso de uso SolicitarClasificacion: reintento manual de la IA (contexto.md 4.10 y 4.12).

Pone estado_ia = PENDIENTE para que el trabajador la tome otra vez; no
cambia el estado de gestión. 409 si ya está PENDIENTE (también mientras el
trabajador la procesa, porque no hay un estado «en proceso») o si la PQRS ya
se respondió o se cerró.
"""

from radica.aplicacion.casos_de_uso.errores import OperacionNoPermitida, PqrsNoEncontrada
from radica.aplicacion.puertos.auditoria import AuditoriaRepository
from radica.aplicacion.puertos.pqrs import PqrsRepository
from radica.dominio.pqrs import EventoAuditoria
from radica.dominio.valores import AccionAuditoria, EstadoIa, EstadoPqrs, OrigenEvento

ESTADOS_SIN_REINTENTO = (EstadoPqrs.RESPONDIDA, EstadoPqrs.CERRADA)
YA_PENDIENTE = "La PQRS ya está pendiente de clasificación con IA."


class SolicitarClasificacion:
    def __init__(self, pqrs: PqrsRepository, auditoria: AuditoriaRepository, id_usuario_actor: int) -> None:
        self._pqrs = pqrs
        self._auditoria = auditoria
        self._id_usuario = id_usuario_actor

    def ejecutar(self, id_pqrs: int) -> EstadoIa:
        datos = self._pqrs.obtener_para_clasificar(id_pqrs)
        if datos is None:
            raise PqrsNoEncontrada(id_pqrs)
        if datos.estado_ia is EstadoIa.PENDIENTE:
            raise OperacionNoPermitida(YA_PENDIENTE)
        if datos.estado in ESTADOS_SIN_REINTENTO:
            raise OperacionNoPermitida(
                f"La PQRS está en estado {datos.estado.value}: ya no se puede clasificar de nuevo."
            )
        if not self._pqrs.marcar_pendiente(id_pqrs, datos.estado_ia):
            # Otra solicitud la dejó en PENDIENTE entre la lectura y el cambio.
            raise OperacionNoPermitida(YA_PENDIENTE)
        self._auditoria.registrar(
            EventoAuditoria(
                id_pqrs,
                OrigenEvento.PERSONA,
                AccionAuditoria.REINTENTO_IA,
                id_usuario=self._id_usuario,
                campo="estado_ia",
                valor_anterior=datos.estado_ia.value,
                valor_nuevo=EstadoIa.PENDIENTE.value,
                motivo="Reintento manual de la clasificación con IA",
            )
        )
        return EstadoIa.PENDIENTE
