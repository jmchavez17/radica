"""Rutas de /api/v1 (contexto.md 4.10). Delgadas: traducen HTTP y llaman al caso de uso.

Cada solicitud abre su unidad de trabajo con la fábrica: la respuesta se arma
después de salir del bloque with, cuando la transacción ya se confirmó.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Response, status

from radica.adaptadores.entrada.api.casos import FabricaDeCasos
from radica.adaptadores.entrada.api.esquemas import (
    ClasificacionSolicitada,
    EventoHistorial,
    Historial,
    PaginaPqrs,
    PqrsCreada,
    PqrsDetalle,
    PqrsNueva,
    PqrsResumen,
    Problema,
    TablaTerminos,
    TerminoLegal,
)
from radica.aplicacion.casos_de_uso.registrar_pqrs import SolicitudRegistro
from radica.aplicacion.puertos.pqrs import FiltroBandeja
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.valores import EstadoPqrs, Semaforo, TipoPqrs

PREFIJO = "/api/v1"

INVALIDA: dict[int | str, dict[str, Any]] = {
    400: {"model": Problema, "description": "Datos faltantes o con formato inválido."}
}
NO_ENCONTRADA: dict[int | str, dict[str, Any]] = {
    404: {"model": Problema, "description": "La PQRS no existe."}
}
CONFLICTO: dict[int | str, dict[str, Any]] = {
    409: {
        "model": Problema,
        "description": "La PQRS ya está PENDIENTE de clasificación o está RESPONDIDA o CERRADA.",
    }
}

IdPqrs = Annotated[int, Path(ge=1, description="Id interno de la PQRS.")]


def crear_rutas(fabrica: FabricaDeCasos) -> APIRouter:
    rutas = APIRouter(prefix=PREFIJO)

    @rutas.post(
        "/pqrs",
        tags=["PQRS"],
        operation_id="registrarPqrs",
        summary="Registrar una PQRS (HU-01)",
        description=(
            "Valida y guarda la PQRS, asigna el radicado, aplica la clasificación provisional por"
            " reglas, calcula el vencimiento y deja la clasificación con IA en PENDIENTE. No espera"
            " a la IA. Rechaza una fecha de radicación posterior al momento del registro."
        ),
        status_code=status.HTTP_201_CREATED,
        response_model=PqrsCreada,
        response_description="PQRS registrada.",
        responses=INVALIDA,
    )
    def registrar_pqrs(entrada: PqrsNueva, response: Response) -> PqrsCreada:
        peticionario = entrada.peticionario
        solicitud = SolicitudRegistro(
            canal=entrada.canal,
            sede=entrada.sede,
            fecha_radicacion=entrada.fecha_radicacion,
            texto=entrada.texto,
            paciente_menor=entrada.paciente_menor_de_edad,
            peticionario=DatosPeticionario(
                tipo_documento=peticionario.tipo_documento,
                numero_documento=peticionario.numero_documento,
                nombre=peticionario.nombre,
                telefono=peticionario.telefono,
                correo=peticionario.correo,
            ),
        )
        with fabrica() as casos:
            registrada = casos.registrar.ejecutar(solicitud)
        response.headers["Location"] = f"{PREFIJO}/pqrs/{registrada.pqrs.id}"
        return PqrsCreada.desde(registrada)

    @rutas.get(
        "/pqrs",
        tags=["PQRS"],
        operation_id="listarPqrs",
        summary="Bandeja de PQRS con semáforo (HU-08)",
        description="Ordenada por vencimiento ascendente: las vencidas quedan primero.",
        response_model=PaginaPqrs,
        response_description="Página de PQRS ordenadas por vencimiento.",
        responses=INVALIDA,
    )
    def listar_pqrs(
        semaforo: Semaforo | None = None,
        estado: EstadoPqrs | None = None,
        id_area: Annotated[int | None, Query(alias="idArea", description="Área sugerida vigente.")] = None,
        tipo: TipoPqrs | None = None,
        pagina: Annotated[int, Query(ge=1)] = 1,
        tamano: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> PaginaPqrs:
        filtro = FiltroBandeja(estado=estado, tipo=tipo, id_area=id_area)
        with fabrica() as casos:
            resultado = casos.bandeja.ejecutar(filtro, semaforo, pagina, tamano)
        return PaginaPqrs(
            pagina=resultado.pagina,
            total=resultado.total,
            elementos=[PqrsResumen.desde(elemento) for elemento in resultado.elementos],
        )

    @rutas.get(
        "/pqrs/{id}",
        tags=["PQRS"],
        operation_id="consultarPqrs",
        summary="Consultar una PQRS con su clasificación vigente y su vencimiento (HU-04, HU-07)",
        description="Solo se muestra el texto enmascarado.",
        response_model=PqrsDetalle,
        response_description="Detalle de la PQRS con el texto enmascarado.",
        responses={**INVALIDA, **NO_ENCONTRADA},
    )
    def consultar_pqrs(id: IdPqrs) -> PqrsDetalle:
        with fabrica() as casos:
            consulta = casos.consultar.ejecutar(id)
        return PqrsDetalle.desde(consulta)

    @rutas.post(
        "/pqrs/{id}/clasificaciones",
        tags=["Clasificación"],
        operation_id="solicitarClasificacionIa",
        summary="Solicitar de nuevo la clasificación con IA (reintento manual)",
        description=(
            "Deja la PQRS con estadoIa PENDIENTE para que el trabajador la clasifique en segundo"
            " plano. No espera a la IA."
        ),
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ClasificacionSolicitada,
        response_description="Solicitud encolada; la PQRS queda en estado de IA PENDIENTE.",
        responses={**INVALIDA, **NO_ENCONTRADA, **CONFLICTO},
    )
    def solicitar_clasificacion_ia(id: IdPqrs) -> ClasificacionSolicitada:
        with fabrica() as casos:
            estado_ia = casos.solicitar_clasificacion.ejecutar(id)
        return ClasificacionSolicitada(id=id, estado_ia=estado_ia)

    @rutas.get(
        "/pqrs/{id}/historial",
        tags=["Tablero"],
        operation_id="consultarHistorial",
        summary="Historial completo de una PQRS (HU-13)",
        description=(
            "Eventos de auditoría en orden cronológico. Los eventos de una sugerencia de la IA"
            " (CLASIFICAR_IA y SUGERENCIA_IA_NO_APLICADA) traen el modelo y la versión de"
            " instrucciones; los demás los traen nulos."
        ),
        response_model=Historial,
        response_description="Eventos de auditoría de la PQRS.",
        responses={**INVALIDA, **NO_ENCONTRADA},
    )
    def consultar_historial(id: IdPqrs) -> Historial:
        with fabrica() as casos:
            eventos = casos.historial.ejecutar(id)
        return Historial(eventos=[EventoHistorial.desde(evento) for evento in eventos])

    @rutas.get(
        "/configuracion/terminos",
        tags=["Configuración"],
        operation_id="listarTerminos",
        summary="Tabla de términos vigente",
        response_model=TablaTerminos,
        response_description="Términos vigentes hoy.",
    )
    def listar_terminos() -> TablaTerminos:
        with fabrica() as casos:
            terminos = casos.terminos.ejecutar()
        return TablaTerminos(terminos=[TerminoLegal.desde(termino) for termino in terminos])

    return rutas
