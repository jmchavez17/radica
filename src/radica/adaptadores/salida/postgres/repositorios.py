"""Repositorios de PostgreSQL (RepositoriosPostgreSQL de la Entrega 2).

SQL explícito con text() y parámetros con nombre; el esquema es el de las
migraciones de Alembic (regla 5), sin modelos ORM. Cada repositorio trabaja
sobre la conexión que recibe: la transacción la abre la raíz de composición,
así que todo un registro se confirma o se deshace junto.
"""

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, text

from radica.aplicacion.puertos.clasificador import AreaCatalogo, AtributoCatalogo, Catalogo
from radica.aplicacion.puertos.pqrs import ClasificacionVigente, FiltroBandeja, VistaPqrs
from radica.dominio.plazos import ZONA_COLOMBIA, Termino
from radica.dominio.pqrs import Clasificacion, EventoAuditoria, PeticionarioCifrado, Pqrs, Referencia
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
    TipoPqrs,
    Unidad,
)


def crear_motor(url: str) -> Engine:
    """hide_parameters evita que un error de SQL lleve valores (datos cifrados, textos) al log."""
    return create_engine(url, hide_parameters=True, pool_pre_ping=True)


def comprobar_conexion(motor: Engine) -> None:
    """Para GET /health: lanza una excepción si la base no responde."""
    with motor.connect() as conexion:
        conexion.execute(text("SELECT 1"))


_COLUMNAS_TERMINO = (
    "t.id_termino, t.regimen, t.tipo_pqrs, t.nivel_riesgo AS termino_nivel, t.poblacion, t.valor,"
    " t.unidad, t.id_calendario, t.fuente_normativa, t.vigente_desde, t.vigente_hasta"
)

_CONSULTA_VISTA = f"""
    SELECT p.id_pqrs, p.radicado, p.canal, p.sede, p.fecha_radicacion, p.texto_enmascarado,
           p.tipo, p.nivel_riesgo, p.estado, p.estado_ia, p.fecha_vencimiento,
           {_COLUMNAS_TERMINO},
           c.origen, c.tipo AS clasificacion_tipo, c.nivel_riesgo AS clasificacion_nivel,
           c.confianza, c.resumen, c.id_atributo, atr.nombre AS atributo_nombre,
           c.id_area, ar.nombre AS area_nombre, l.modelo, l.version_instrucciones,
           u.id_usuario AS id_responsable, u.nombre AS responsable_nombre
      FROM pqrs p
      JOIN termino_legal t ON t.id_termino = p.id_termino
      LEFT JOIN clasificacion c ON c.id_pqrs = p.id_pqrs AND c.vigente
      LEFT JOIN atributo_calidad atr ON atr.id_atributo = c.id_atributo
      LEFT JOIN area ar ON ar.id_area = c.id_area
      LEFT JOIN llamada_ia l ON l.id_llamada = c.id_llamada_ia
      LEFT JOIN usuario u ON u.id_usuario = p.id_responsable
"""


def _termino(fila: Mapping[str, Any]) -> Termino:
    return Termino(
        id=fila["id_termino"],
        regimen=Regimen(fila["regimen"]),
        tipo_pqrs=TipoPqrs(fila["tipo_pqrs"]),
        nivel_riesgo=NivelRiesgo(fila["termino_nivel"]),
        poblacion=Poblacion(fila["poblacion"]),
        valor=fila["valor"],
        unidad=Unidad(fila["unidad"]),
        id_calendario=fila["id_calendario"],
        fuente_normativa=fila["fuente_normativa"],
        vigente_desde=fila["vigente_desde"],
        vigente_hasta=fila["vigente_hasta"],
    )


def _referencia(id_: int | None, nombre: str | None) -> Referencia | None:
    return Referencia(id_, nombre) if id_ is not None and nombre is not None else None


def _vista(fila: Mapping[str, Any]) -> VistaPqrs:
    clasificacion = None
    if fila["origen"] is not None:
        clasificacion = ClasificacionVigente(
            origen=OrigenClasificacion(fila["origen"]),
            tipo=TipoPqrs(fila["clasificacion_tipo"]),
            atributo=_referencia(fila["id_atributo"], fila["atributo_nombre"]),
            area=_referencia(fila["id_area"], fila["area_nombre"]),
            nivel_riesgo=NivelRiesgo(fila["clasificacion_nivel"]),
            confianza=float(fila["confianza"]),
            resumen=fila["resumen"],
            modelo=fila["modelo"],
            version_instrucciones=fila["version_instrucciones"],
        )
    return VistaPqrs(
        id=fila["id_pqrs"],
        radicado=fila["radicado"],
        canal=Canal(fila["canal"]),
        sede=fila["sede"],
        fecha_radicacion=fila["fecha_radicacion"].astimezone(ZONA_COLOMBIA),
        texto_enmascarado=fila["texto_enmascarado"],
        tipo=TipoPqrs(fila["tipo"]),
        nivel_riesgo=NivelRiesgo(fila["nivel_riesgo"]),
        estado=EstadoPqrs(fila["estado"]),
        estado_ia=EstadoIa(fila["estado_ia"]),
        fecha_vencimiento=fila["fecha_vencimiento"].astimezone(ZONA_COLOMBIA),
        termino=_termino(fila),
        clasificacion=clasificacion,
        responsable=_referencia(fila["id_responsable"], fila["responsable_nombre"]),
    )


class PqrsRepositoryPostgres:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def reservar_id(self) -> int:
        return self._conexion.execute(
            text("SELECT nextval(pg_get_serial_sequence('pqrs', 'id_pqrs'))")
        ).scalar_one()

    def obtener_o_crear_peticionario(self, peticionario: PeticionarioCifrado) -> int:
        parametros = {
            "hash": peticionario.documento_hash,
            "nombre": peticionario.nombre_cifrado,
            "contacto": peticionario.contacto_cifrado,
        }
        nuevo = self._conexion.execute(
            text(
                "INSERT INTO peticionario (documento_hash, nombre_cifrado, contacto_cifrado)"
                " VALUES (:hash, :nombre, :contacto)"
                " ON CONFLICT (documento_hash) DO NOTHING RETURNING id_peticionario"
            ),
            parametros,
        ).scalar_one_or_none()
        if nuevo is not None:
            return nuevo
        return self._conexion.execute(
            text("SELECT id_peticionario FROM peticionario WHERE documento_hash = :hash"),
            {"hash": peticionario.documento_hash},
        ).scalar_one()

    def guardar(self, pqrs: Pqrs) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO pqrs (id_pqrs, radicado, id_peticionario, canal, sede, fecha_radicacion,"
                " texto_original_cifrado, texto_enmascarado, tipo, id_atributo, nivel_riesgo,"
                " paciente_menor, id_termino, fecha_vencimiento, estado, estado_ia)"
                " VALUES (:id, :radicado, :id_peticionario, :canal, :sede, :fecha_radicacion,"
                " :texto_cifrado, :texto_enmascarado, :tipo, :id_atributo, :nivel_riesgo,"
                " :paciente_menor, :id_termino, :fecha_vencimiento, :estado, :estado_ia)"
            ),
            {
                "id": pqrs.id,
                "radicado": pqrs.radicado,
                "id_peticionario": pqrs.id_peticionario,
                "canal": pqrs.canal.value,
                "sede": pqrs.sede,
                "fecha_radicacion": pqrs.fecha_radicacion,
                "texto_cifrado": pqrs.texto_original_cifrado,
                "texto_enmascarado": pqrs.texto_enmascarado,
                "tipo": pqrs.tipo.value,
                "id_atributo": pqrs.id_atributo,
                "nivel_riesgo": pqrs.nivel_riesgo.value,
                "paciente_menor": pqrs.paciente_menor,
                "id_termino": pqrs.id_termino,
                "fecha_vencimiento": pqrs.fecha_vencimiento,
                "estado": pqrs.estado.value,
                "estado_ia": pqrs.estado_ia.value,
            },
        )

    def guardar_clasificacion(self, id_pqrs: int, clasificacion: Clasificacion) -> int:
        datos = clasificacion.datos_extraidos
        return self._conexion.execute(
            text(
                "INSERT INTO clasificacion (id_pqrs, id_llamada_ia, origen, tipo, id_atributo,"
                " id_area, nivel_riesgo, confianza, resumen, datos_extraidos, vigente)"
                " VALUES (:id_pqrs, :id_llamada_ia, :origen, :tipo, :id_atributo, :id_area,"
                " :nivel_riesgo, :confianza, :resumen, CAST(:datos AS JSONB), :vigente)"
                " RETURNING id_clasificacion"
            ),
            {
                "id_pqrs": id_pqrs,
                "id_llamada_ia": clasificacion.id_llamada_ia,
                "origen": clasificacion.origen.value,
                "tipo": clasificacion.tipo.value,
                "id_atributo": clasificacion.id_atributo,
                "id_area": clasificacion.id_area,
                "nivel_riesgo": clasificacion.nivel_riesgo.value,
                "confianza": clasificacion.confianza,
                "resumen": clasificacion.resumen,
                "datos": json.dumps(dict(datos), ensure_ascii=False) if datos is not None else None,
                "vigente": clasificacion.vigente,
            },
        ).scalar_one()

    def obtener(self, id_pqrs: int) -> VistaPqrs | None:
        fila = (
            self._conexion.execute(text(_CONSULTA_VISTA + " WHERE p.id_pqrs = :id"), {"id": id_pqrs})
            .mappings()
            .one_or_none()
        )
        return _vista(fila) if fila is not None else None

    def listar(self, filtro: FiltroBandeja) -> list[VistaPqrs]:
        condiciones: list[str] = []
        parametros: dict[str, Any] = {}
        if filtro.estado is not None:
            condiciones.append("p.estado = :estado")
            parametros["estado"] = filtro.estado.value
        if filtro.tipo is not None:
            condiciones.append("p.tipo = :tipo")
            parametros["tipo"] = filtro.tipo.value
        if filtro.id_area is not None:
            condiciones.append("c.id_area = :id_area")
            parametros["id_area"] = filtro.id_area
        donde = " WHERE " + " AND ".join(condiciones) if condiciones else ""
        filas = self._conexion.execute(
            text(_CONSULTA_VISTA + donde + " ORDER BY p.fecha_vencimiento, p.id_pqrs"), parametros
        ).mappings()
        return [_vista(fila) for fila in filas]

    def existe(self, id_pqrs: int) -> bool:
        return (
            self._conexion.execute(
                text("SELECT 1 FROM pqrs WHERE id_pqrs = :id"), {"id": id_pqrs}
            ).scalar_one_or_none()
            is not None
        )


class AuditoriaRepositoryPostgres:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def registrar(self, evento: EventoAuditoria) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO auditoria (id_pqrs, id_usuario, origen, accion, campo, valor_anterior,"
                " valor_nuevo, motivo) VALUES (:id_pqrs, :id_usuario, :origen, :accion, :campo,"
                " :valor_anterior, :valor_nuevo, :motivo)"
            ),
            {
                "id_pqrs": evento.id_pqrs,
                "id_usuario": evento.id_usuario,
                "origen": evento.origen.value,
                "accion": evento.accion.value,
                "campo": evento.campo,
                "valor_anterior": evento.valor_anterior,
                "valor_nuevo": evento.valor_nuevo,
                "motivo": evento.motivo,
            },
        )

    def historial(self, id_pqrs: int) -> list[EventoAuditoria]:
        filas = self._conexion.execute(
            text(
                "SELECT id_evento, id_pqrs, id_usuario, origen, accion, campo, valor_anterior,"
                " valor_nuevo, motivo, fecha FROM auditoria WHERE id_pqrs = :id"
                " ORDER BY fecha, id_evento"
            ),
            {"id": id_pqrs},
        ).mappings()
        return [
            EventoAuditoria(
                id_pqrs=fila["id_pqrs"],
                origen=OrigenEvento(fila["origen"]),
                accion=AccionAuditoria(fila["accion"]),
                id_usuario=fila["id_usuario"],
                campo=fila["campo"],
                valor_anterior=fila["valor_anterior"],
                valor_nuevo=fila["valor_nuevo"],
                motivo=fila["motivo"],
                id_evento=fila["id_evento"],
                fecha=fila["fecha"].astimezone(ZONA_COLOMBIA),
            )
            for fila in filas
        ]


class ConfiguracionRepositoryPostgres:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def terminos_vigentes(self, dia: date) -> tuple[Termino, ...]:
        filas = self._conexion.execute(
            text(
                f"SELECT {_COLUMNAS_TERMINO} FROM termino_legal t"
                " WHERE t.vigente_desde <= :dia AND (t.vigente_hasta IS NULL OR t.vigente_hasta >= :dia)"
                " ORDER BY t.id_termino"
            ),
            {"dia": dia},
        ).mappings()
        return tuple(_termino(fila) for fila in filas)

    def festivos(self, id_calendario: int) -> frozenset[date]:
        filas = self._conexion.execute(
            text("SELECT fecha FROM festivo WHERE id_calendario = :id"), {"id": id_calendario}
        ).scalars()
        return frozenset(filas)

    def catalogo(self) -> Catalogo:
        atributos = self._conexion.execute(
            text(
                "SELECT id_atributo, nombre, definicion FROM atributo_calidad"
                " WHERE activo ORDER BY id_atributo"
            )
        ).all()
        areas = self._conexion.execute(
            text("SELECT id_area, nombre FROM area WHERE activa ORDER BY id_area")
        ).all()
        return Catalogo(
            tipos=tuple(TipoPqrs),
            atributos=tuple(AtributoCatalogo(*fila) for fila in atributos),
            areas=tuple(AreaCatalogo(*fila) for fila in areas),
        )
