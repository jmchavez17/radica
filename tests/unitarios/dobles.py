"""Dobles en memoria de los puertos, para probar los casos de uso sin base de datos."""

import json
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import anthropic

from radica.aplicacion.puertos.clasificador import (
    AreaCatalogo,
    AtributoCatalogo,
    Catalogo,
    ResultadoClasificacion,
    SolicitudClasificacion,
    UsoIA,
)
from radica.aplicacion.puertos.pqrs import FiltroBandeja, PqrsParaClasificar, VistaPqrs
from radica.dominio.plazos import Termino
from radica.dominio.pqrs import Clasificacion, EventoAuditoria, PeticionarioCifrado, Pqrs
from radica.dominio.valores import EstadoIa, EstadoPqrs, NivelRiesgo, TipoPqrs

CATALOGO = Catalogo(
    tipos=tuple(TipoPqrs),
    atributos=(
        AtributoCatalogo(1, "Calidad humana", "Trato del personal hacia el usuario"),
        AtributoCatalogo(2, "Oportunidad", "Demora en obtener una cita, un examen o una autorización"),
        AtributoCatalogo(5, "Medicamentos", "Entrega incompleta, tardía o equivocada de medicamentos"),
    ),
    areas=(
        AreaCatalogo(1, "Atención al usuario"),
        AreaCatalogo(2, "Citas"),
        AreaCatalogo(4, "Autorizaciones"),
        AreaCatalogo(6, "Farmacia"),
    ),
)


class PqrsEnMemoria:
    def __init__(self, primer_id: int = 1287) -> None:
        self._siguiente = primer_id
        self.peticionarios: dict[str, tuple[int, PeticionarioCifrado]] = {}
        self.pqrs: dict[int, Pqrs] = {}
        self.clasificaciones: list[tuple[int, Clasificacion]] = []
        self.vistas: dict[int, VistaPqrs] = {}
        self.ids_reservados: list[int] = []

    def reservar_id(self) -> int:
        id_pqrs = self._siguiente
        self._siguiente += 1
        self.ids_reservados.append(id_pqrs)
        return id_pqrs

    def obtener_o_crear_peticionario(self, peticionario: PeticionarioCifrado) -> int:
        if peticionario.documento_hash not in self.peticionarios:
            nuevo = (len(self.peticionarios) + 1, peticionario)
            self.peticionarios[peticionario.documento_hash] = nuevo
        return self.peticionarios[peticionario.documento_hash][0]

    def guardar(self, pqrs: Pqrs) -> None:
        self.pqrs[pqrs.id] = pqrs

    def guardar_clasificacion(self, id_pqrs: int, clasificacion: Clasificacion) -> int:
        if clasificacion.vigente and self.vigente(id_pqrs) is not None:
            # Igual que el índice único parcial de la base: una sola vigente por PQRS.
            raise ValueError(f"La PQRS {id_pqrs} ya tiene una clasificación vigente.")
        self.clasificaciones.append((id_pqrs, clasificacion))
        return len(self.clasificaciones)

    def vigente(self, id_pqrs: int) -> Clasificacion | None:
        return next(
            (clasificacion for id_, clasificacion in self.clasificaciones
             if id_ == id_pqrs and clasificacion.vigente),
            None,
        )

    def de(self, id_pqrs: int) -> list[Clasificacion]:
        return [clasificacion for id_, clasificacion in self.clasificaciones if id_ == id_pqrs]

    def pendientes_de_ia(self, limite: int = 1) -> list[int]:
        pendientes = sorted(
            id_ for id_, pqrs in self.pqrs.items() if pqrs.estado_ia is EstadoIa.PENDIENTE
        )
        return pendientes[:limite]

    def obtener_para_clasificar(self, id_pqrs: int) -> PqrsParaClasificar | None:
        pqrs = self.pqrs.get(id_pqrs)
        if pqrs is None:
            return None
        peticionario = next(
            cifrado for id_, cifrado in self.peticionarios.values() if id_ == pqrs.id_peticionario
        )
        vigente = self.vigente(id_pqrs)
        return PqrsParaClasificar(
            id=pqrs.id,
            fecha_radicacion=pqrs.fecha_radicacion,
            texto_enmascarado=pqrs.texto_enmascarado,
            paciente_menor=pqrs.paciente_menor,
            tipo=pqrs.tipo,
            id_atributo=pqrs.id_atributo,
            id_area=vigente.id_area if vigente else None,
            nivel_riesgo=pqrs.nivel_riesgo,
            fecha_vencimiento=pqrs.fecha_vencimiento,
            estado=pqrs.estado,
            estado_ia=pqrs.estado_ia,
            peticionario=peticionario,
        )

    def retirar_clasificacion_vigente(self, id_pqrs: int) -> None:
        self.clasificaciones = [
            (id_, replace(clasificacion, vigente=False) if id_ == id_pqrs else clasificacion)
            for id_, clasificacion in self.clasificaciones
        ]

    def actualizar_clasificacion(
        self,
        id_pqrs: int,
        tipo: TipoPqrs,
        id_atributo: int | None,
        nivel_riesgo: NivelRiesgo,
        id_termino: int,
        fecha_vencimiento: datetime,
    ) -> None:
        self.pqrs[id_pqrs] = replace(
            self.pqrs[id_pqrs],
            tipo=tipo,
            id_atributo=id_atributo,
            nivel_riesgo=nivel_riesgo,
            id_termino=id_termino,
            fecha_vencimiento=fecha_vencimiento,
        )

    def actualizar_estado(self, id_pqrs: int, estado: EstadoPqrs, estado_ia: EstadoIa) -> None:
        self.pqrs[id_pqrs] = replace(self.pqrs[id_pqrs], estado=estado, estado_ia=estado_ia)

    def marcar_pendiente(self, id_pqrs: int, estado_ia_actual: EstadoIa) -> bool:
        if self.pqrs[id_pqrs].estado_ia is not estado_ia_actual:
            return False
        self.pqrs[id_pqrs] = replace(self.pqrs[id_pqrs], estado_ia=EstadoIa.PENDIENTE)
        return True

    def agregar_vista(self, vista: VistaPqrs) -> None:
        self.vistas[vista.id] = vista

    def obtener(self, id_pqrs: int) -> VistaPqrs | None:
        return self.vistas.get(id_pqrs)

    def listar(self, filtro: FiltroBandeja) -> list[VistaPqrs]:
        def cumple(vista: VistaPqrs) -> bool:
            area = vista.clasificacion.area.id if vista.clasificacion and vista.clasificacion.area else None
            return (
                (filtro.estado is None or vista.estado is filtro.estado)
                and (filtro.tipo is None or vista.tipo is filtro.tipo)
                and (filtro.id_area is None or area == filtro.id_area)
            )

        elegidas = [vista for vista in self.vistas.values() if cumple(vista)]
        return sorted(elegidas, key=lambda vista: (vista.fecha_vencimiento, vista.id))

    def existe(self, id_pqrs: int) -> bool:
        return id_pqrs in self.vistas or id_pqrs in self.pqrs


class AuditoriaEnMemoria:
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []
        self.llamadas: list[tuple[int, UsoIA, str]] = []

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(replace(evento, id_evento=len(self.eventos) + 1))

    def historial(self, id_pqrs: int) -> list[EventoAuditoria]:
        return [evento for evento in self.eventos if evento.id_pqrs == id_pqrs]

    def registrar_llamada_ia(self, id_pqrs: int, uso: UsoIA, version_instrucciones: str) -> int:
        self.llamadas.append((id_pqrs, uso, version_instrucciones))
        return len(self.llamadas)


class ConfiguracionEnMemoria:
    def __init__(self, terminos: tuple[Termino, ...], festivos: frozenset[date]) -> None:
        self._terminos = terminos
        self._festivos = festivos
        self.dias_consultados: list[date] = []

    def terminos_vigentes(self, dia: date) -> tuple[Termino, ...]:
        self.dias_consultados.append(dia)
        return tuple(termino for termino in self._terminos if termino.vigente_en(dia))

    def festivos(self, id_calendario: int) -> frozenset[date]:
        return self._festivos if id_calendario == 1 else frozenset()

    def catalogo(self) -> Catalogo:
        return CATALOGO


class ClasificadorFijo:
    """Responde siempre lo mismo y guarda las solicitudes que recibió."""

    def __init__(self, resultado: ResultadoClasificacion) -> None:
        self.resultado = resultado
        self.solicitudes: list[SolicitudClasificacion] = []

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        self.solicitudes.append(solicitud)
        return self.resultado


class ClasificadorQueFalla:
    """Lanza siempre el error dado (ProveedorNoDisponible o SalidaInvalida) y cuenta las llamadas."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.solicitudes: list[SolicitudClasificacion] = []

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        self.solicitudes.append(solicitud)
        raise self.error


# --- Cliente falso del SDK de Anthropic: sin red y sin la clave real ---

SALIDA_CLAUDE = {
    "tipo": "RECLAMO",
    "idAtributo": 2,
    "idArea": 4,
    "nivelRiesgo": "PRIORIZADO",
    "confianza": 0.86,
    "senalesRiesgo": ["tres semanas sin autorización de un examen ordenado"],
    "resumen": "Paciente espera hace tres semanas la autorización de una resonancia.",
    "datosClave": [
        {"nombre": "servicio", "valor": "resonancia"},
        {"nombre": "tiempoEspera", "valor": "tres semanas"},
    ],
}


def mensaje_claude(
    salida: object = SALIDA_CLAUDE,
    stop_reason: str = "end_turn",
    tokens: tuple[int, int] = (3000, 300),
) -> anthropic.types.Message:
    """Una respuesta real del tipo Message del SDK, para que un cambio del SDK se note."""
    texto = salida if isinstance(salida, str) else json.dumps(salida, ensure_ascii=False)
    return anthropic.types.Message.model_validate(
        {
            "id": "msg_prueba",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": texto}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]},
        }
    )


class ClienteClaudeFalso:
    """Responde en orden lo que se le da: un Message o una excepción para lanzar."""

    def __init__(self, *respuestas: object) -> None:
        self.respuestas = list(respuestas)
        self.llamadas: list[dict[str, Any]] = []

    @property
    def messages(self) -> "ClienteClaudeFalso":
        return self

    def create(self, **parametros: Any) -> anthropic.types.Message:
        self.llamadas.append(parametros)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, BaseException):
            raise respuesta
        return respuesta  # type: ignore[return-value]
