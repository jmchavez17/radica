"""Dobles en memoria de los puertos, para probar los casos de uso sin base de datos."""

from dataclasses import replace
from datetime import date

from radica.aplicacion.puertos.clasificador import (
    AreaCatalogo,
    AtributoCatalogo,
    Catalogo,
    ResultadoClasificacion,
    SolicitudClasificacion,
)
from radica.aplicacion.puertos.pqrs import FiltroBandeja, VistaPqrs
from radica.dominio.plazos import Termino
from radica.dominio.pqrs import Clasificacion, EventoAuditoria, PeticionarioCifrado, Pqrs
from radica.dominio.valores import TipoPqrs

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
        self.clasificaciones.append((id_pqrs, clasificacion))
        return len(self.clasificaciones)

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

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(replace(evento, id_evento=len(self.eventos) + 1))

    def historial(self, id_pqrs: int) -> list[EventoAuditoria]:
        return [evento for evento in self.eventos if evento.id_pqrs == id_pqrs]


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
