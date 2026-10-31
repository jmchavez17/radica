"""Esquemas de entrada y salida del contrato docs/api/radica-api-v0.1.yaml.

Nombres en camelCase en el JSON y en snake_case en Python. Los textos se
recortan; un opcional vacío cuenta como ausente. Las salidas nunca llevan datos
del peticionario.
"""

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from radica.aplicacion.casos_de_uso.resultados import PqrsConSemaforo
from radica.aplicacion.puertos.pqrs import ClasificacionVigente
from radica.dominio.plazos import Termino
from radica.dominio.pqrs import EventoAuditoria, Referencia as ReferenciaDominio
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    Poblacion,
    Regimen,
    Semaforo,
    TipoDocumento,
    TipoPqrs,
    Unidad,
)

# Correo con forma usuario@dominio.tld; sin dependencia nueva (duda 3 de la sesión 2).
PATRON_CORREO = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$"

EJEMPLO_REGISTRO = {
    "canal": "DIME",
    "sede": "Sede clínica",
    "fechaRadicacion": "2026-10-30T16:00:00-05:00",
    "texto": (
        "Desde hace tres semanas me ordenaron una resonancia y no me han dado la autorización."
        " Llamé dos veces y nadie responde. Mi teléfono es 3000000000."
    ),
    "pacienteMenorDeEdad": False,
    "peticionario": {
        "tipoDocumento": "CC",
        "numeroDocumento": "1000000001",
        "nombre": "Usuario Sintético Uno",
        "telefono": "3000000000",
        "correo": "usuario1@ejemplo.com",
    },
}


class _Esquema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _Entrada(_Esquema):
    model_config = ConfigDict(str_strip_whitespace=True)


def _vacio_es_ausente(valor: Any) -> Any:
    return None if isinstance(valor, str) and not valor.strip() else valor


class Peticionario(_Entrada):
    tipo_documento: TipoDocumento
    numero_documento: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(min_length=1, max_length=150)]
    telefono: Annotated[str | None, Field(max_length=20)] = None
    correo: Annotated[str | None, Field(pattern=PATRON_CORREO)] = None

    @field_validator("telefono", "correo", mode="before")
    @classmethod
    def _opcionales(cls, valor: Any) -> Any:
        return _vacio_es_ausente(valor)


class PqrsNueva(_Entrada):
    model_config = ConfigDict(json_schema_extra={"examples": [EJEMPLO_REGISTRO]})

    canal: Canal
    sede: Annotated[str | None, Field(max_length=60)] = None
    fecha_radicacion: AwareDatetime
    texto: Annotated[str, Field(min_length=10, max_length=10000)]
    paciente_menor_de_edad: bool = False
    peticionario: Peticionario

    @field_validator("sede", mode="before")
    @classmethod
    def _opcionales(cls, valor: Any) -> Any:
        return _vacio_es_ausente(valor)


class Referencia(_Esquema):
    id: int
    nombre: str

    @classmethod
    def desde(cls, referencia: ReferenciaDominio | None) -> "Referencia | None":
        return cls(id=referencia.id, nombre=referencia.nombre) if referencia else None


class ClasificacionResumen(_Esquema):
    origen: OrigenClasificacion
    tipo: TipoPqrs
    atributo: Referencia | None
    area: Referencia | None
    nivel_riesgo: NivelRiesgo
    confianza: float
    resumen: str | None
    requiere_revision: bool
    modelo: str | None
    version_instrucciones: str | None

    @classmethod
    def desde(cls, clasificacion: ClasificacionVigente | None, estado: EstadoPqrs) -> "ClasificacionResumen | None":
        if clasificacion is None:
            return None
        return cls(
            origen=clasificacion.origen,
            tipo=clasificacion.tipo,
            atributo=Referencia.desde(clasificacion.atributo),
            area=Referencia.desde(clasificacion.area),
            nivel_riesgo=clasificacion.nivel_riesgo,
            confianza=clasificacion.confianza,
            resumen=clasificacion.resumen,
            requiere_revision=estado is EstadoPqrs.REQUIERE_REVISION,
            modelo=clasificacion.modelo,
            version_instrucciones=clasificacion.version_instrucciones,
        )


class Vencimiento(_Esquema):
    fecha: datetime
    regla: str
    semaforo: Semaforo
    horas_restantes: float

    @classmethod
    def desde(cls, consulta: PqrsConSemaforo) -> "Vencimiento":
        return cls(
            fecha=consulta.pqrs.fecha_vencimiento,
            regla=consulta.pqrs.termino.regla,
            semaforo=consulta.semaforo.color,
            horas_restantes=consulta.semaforo.horas_restantes,
        )


class PqrsCreada(_Esquema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1287,
                    "radicado": "RAD-2026-001287",
                    "estado": "REGISTRADA",
                    "estadoIa": "PENDIENTE",
                    "clasificacionProvisional": {
                        "origen": "REGLAS",
                        "tipo": "RECLAMO",
                        "atributo": None,
                        "area": {"id": 4, "nombre": "Autorizaciones"},
                        "nivelRiesgo": "SIMPLE",
                        "confianza": 0.5,
                        "resumen": None,
                        "requiereRevision": False,
                        "modelo": None,
                        "versionInstrucciones": None,
                    },
                    "vencimiento": {
                        "fecha": "2026-11-02T16:00:00-05:00",
                        "regla": "Reclamo en salud, riesgo simple: 72 horas corridas",
                        "semaforo": "VERDE",
                        "horasRestantes": 70.0,
                    },
                    "posiblesDuplicados": [],
                }
            ]
        }
    )

    id: int
    radicado: str
    estado: EstadoPqrs
    estado_ia: EstadoIa
    clasificacion_provisional: ClasificacionResumen | None
    vencimiento: Vencimiento
    posibles_duplicados: list[str] = Field(
        default_factory=list, description="La detección de duplicados no está en esta entrega."
    )

    @classmethod
    def desde(cls, consulta: PqrsConSemaforo) -> "PqrsCreada":
        pqrs = consulta.pqrs
        return cls(
            id=pqrs.id,
            radicado=pqrs.radicado,
            estado=pqrs.estado,
            estado_ia=pqrs.estado_ia,
            clasificacion_provisional=ClasificacionResumen.desde(pqrs.clasificacion, pqrs.estado),
            vencimiento=Vencimiento.desde(consulta),
        )


class PqrsResumen(_Esquema):
    id: int
    radicado: str
    tipo: TipoPqrs
    nivel_riesgo: NivelRiesgo
    area: Referencia | None = Field(description="Área sugerida de la clasificación vigente.")
    estado: EstadoPqrs
    vencimiento: Vencimiento

    @classmethod
    def desde(cls, consulta: PqrsConSemaforo) -> "PqrsResumen":
        pqrs = consulta.pqrs
        return cls(
            id=pqrs.id,
            radicado=pqrs.radicado,
            tipo=pqrs.tipo,
            nivel_riesgo=pqrs.nivel_riesgo,
            area=Referencia.desde(pqrs.clasificacion.area if pqrs.clasificacion else None),
            estado=pqrs.estado,
            vencimiento=Vencimiento.desde(consulta),
        )


class PaginaPqrs(_Esquema):
    pagina: int
    total: int
    elementos: list[PqrsResumen]


class PqrsDetalle(_Esquema):
    id: int
    radicado: str
    canal: Canal
    sede: str | None
    fecha_radicacion: datetime
    texto_enmascarado: str
    estado: EstadoPqrs
    estado_ia: EstadoIa
    clasificacion: ClasificacionResumen | None
    vencimiento: Vencimiento
    responsable: Referencia | None
    posibles_duplicados: list[str] = Field(default_factory=list)

    @classmethod
    def desde(cls, consulta: PqrsConSemaforo) -> "PqrsDetalle":
        pqrs = consulta.pqrs
        return cls(
            id=pqrs.id,
            radicado=pqrs.radicado,
            canal=pqrs.canal,
            sede=pqrs.sede,
            fecha_radicacion=pqrs.fecha_radicacion,
            texto_enmascarado=pqrs.texto_enmascarado,
            estado=pqrs.estado,
            estado_ia=pqrs.estado_ia,
            clasificacion=ClasificacionResumen.desde(pqrs.clasificacion, pqrs.estado),
            vencimiento=Vencimiento.desde(consulta),
            responsable=Referencia.desde(pqrs.responsable),
        )


class EventoHistorial(_Esquema):
    id: int | None
    fecha: datetime | None
    origen: OrigenEvento
    accion: AccionAuditoria
    id_usuario: int | None
    campo: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    motivo: str | None
    modelo: str | None = Field(
        default=None, description="Solo en eventos de IA; la tabla auditoria aún no lo guarda."
    )
    version_instrucciones: str | None = Field(
        default=None, description="Solo en eventos de IA; la tabla auditoria aún no lo guarda."
    )

    @classmethod
    def desde(cls, evento: EventoAuditoria) -> "EventoHistorial":
        return cls(
            id=evento.id_evento,
            fecha=evento.fecha,
            origen=evento.origen,
            accion=evento.accion,
            id_usuario=evento.id_usuario,
            campo=evento.campo,
            valor_anterior=evento.valor_anterior,
            valor_nuevo=evento.valor_nuevo,
            motivo=evento.motivo,
        )


class Historial(_Esquema):
    eventos: list[EventoHistorial]


class TerminoLegal(_Esquema):
    id: int
    regimen: Regimen
    tipo: TipoPqrs
    nivel_riesgo: NivelRiesgo
    poblacion: Poblacion
    valor: int
    unidad: Unidad
    id_calendario: int | None
    fuente_normativa: str
    vigente_desde: date
    vigente_hasta: date | None
    regla: str

    @classmethod
    def desde(cls, termino: Termino) -> "TerminoLegal":
        return cls(
            id=termino.id,
            regimen=termino.regimen,
            tipo=termino.tipo_pqrs,
            nivel_riesgo=termino.nivel_riesgo,
            poblacion=termino.poblacion,
            valor=termino.valor,
            unidad=termino.unidad,
            id_calendario=termino.id_calendario,
            fuente_normativa=termino.fuente_normativa,
            vigente_desde=termino.vigente_desde,
            vigente_hasta=termino.vigente_hasta,
            regla=termino.regla,
        )


class TablaTerminos(_Esquema):
    terminos: list[TerminoLegal]


class ErrorCampo(BaseModel):
    campo: str
    mensaje: str


class Problema(BaseModel):
    """Problem Details (RFC 9457)."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    errores: list[ErrorCampo] | None = None
