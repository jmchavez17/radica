"""Repositorios de PostgreSQL contra una base temporal migrada.

Cada prueba trabaja dentro de una transacción que se deshace al final.
"""

from collections.abc import Iterator
from datetime import date, datetime

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from radica.adaptadores.salida.postgres.repositorios import (
    AuditoriaRepositoryPostgres,
    ConfiguracionRepositoryPostgres,
    PqrsRepositoryPostgres,
    comprobar_conexion,
)
from radica.aplicacion.puertos.pqrs import FiltroBandeja
from radica.dominio.plazos import ZONA_COLOMBIA
from radica.dominio.pqrs import (
    Clasificacion,
    EventoAuditoria,
    PeticionarioCifrado,
    Pqrs,
    Referencia,
    formato_radicado,
)
from radica.dominio.valores import (
    AccionAuditoria,
    Canal,
    EstadoIa,
    EstadoPqrs,
    NivelRiesgo,
    OrigenClasificacion,
    OrigenEvento,
    TipoPqrs,
)

RADICACION = datetime(2026, 10, 30, 16, tzinfo=ZONA_COLOMBIA)


@pytest.fixture
def conexion(motor_migrado: Engine) -> Iterator[Connection]:
    with motor_migrado.connect() as conexion:
        transaccion = conexion.begin()
        try:
            yield conexion
        finally:
            transaccion.rollback()


def _peticionario(huella: str = "a" * 64, nombre: bytes = b"nombre-cifrado") -> PeticionarioCifrado:
    return PeticionarioCifrado(huella, nombre, b"contacto-cifrado")


def _registrar(
    repositorio: PqrsRepositoryPostgres,
    tipo: TipoPqrs = TipoPqrs.RECLAMO,
    nivel: NivelRiesgo = NivelRiesgo.SIMPLE,
    id_termino: int = 6,
    vencimiento: datetime = datetime(2026, 11, 2, 16, tzinfo=ZONA_COLOMBIA),
    id_area: int | None = 4,
    estado: EstadoPqrs = EstadoPqrs.REGISTRADA,
) -> int:
    id_pqrs = repositorio.reservar_id()
    repositorio.guardar(
        Pqrs(
            id=id_pqrs,
            radicado=formato_radicado(id_pqrs, RADICACION),
            id_peticionario=repositorio.obtener_o_crear_peticionario(_peticionario()),
            canal=Canal.DIME,
            sede="Sede clínica",
            fecha_radicacion=RADICACION,
            texto_original_cifrado=b"texto-cifrado",
            texto_enmascarado="Mi teléfono es [TELEFONO_1].",
            tipo=tipo,
            id_atributo=2 if id_area else None,
            nivel_riesgo=nivel,
            paciente_menor=False,
            id_termino=id_termino,
            fecha_vencimiento=vencimiento,
            estado=estado,
            estado_ia=EstadoIa.PENDIENTE,
        )
    )
    repositorio.guardar_clasificacion(
        id_pqrs,
        Clasificacion(
            OrigenClasificacion.REGLAS, tipo, 2 if id_area else None, id_area, nivel, 0.5,
            datos_extraidos={"servicio": "resonancia"},
        ),
    )
    return id_pqrs


def test_la_conexion_responde(motor_migrado: Engine) -> None:
    comprobar_conexion(motor_migrado)


def test_reservar_id_usa_la_secuencia(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    primero, segundo = repositorio.reservar_id(), repositorio.reservar_id()
    assert segundo == primero + 1


def test_el_peticionario_se_reutiliza_sin_sobrescribir(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)

    primero = repositorio.obtener_o_crear_peticionario(_peticionario(nombre=b"original"))
    segundo = repositorio.obtener_o_crear_peticionario(_peticionario(nombre=b"otro"))

    assert primero == segundo
    nombre = conexion.execute(
        text("SELECT nombre_cifrado FROM peticionario WHERE id_peticionario = :id"), {"id": primero}
    ).scalar_one()
    assert bytes(nombre) == b"original"
    assert repositorio.obtener_o_crear_peticionario(_peticionario("b" * 64)) != primero


def test_guardar_y_obtener(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    id_pqrs = _registrar(repositorio)

    vista = repositorio.obtener(id_pqrs)

    assert vista is not None
    assert vista.radicado == f"RAD-2026-{id_pqrs:06d}"
    assert (vista.canal, vista.sede, vista.estado, vista.estado_ia) == (
        Canal.DIME, "Sede clínica", EstadoPqrs.REGISTRADA, EstadoIa.PENDIENTE,
    )
    assert vista.fecha_radicacion == RADICACION
    assert vista.fecha_radicacion.utcoffset() == ZONA_COLOMBIA.utcoffset(RADICACION)
    assert vista.fecha_vencimiento == datetime(2026, 11, 2, 16, tzinfo=ZONA_COLOMBIA)
    assert vista.termino.regla == "Reclamo en salud, riesgo simple: 72 horas corridas"
    assert vista.clasificacion is not None
    assert vista.clasificacion.origen is OrigenClasificacion.REGLAS
    assert vista.clasificacion.area == Referencia(4, "Autorizaciones")
    assert vista.clasificacion.atributo == Referencia(2, "Oportunidad")
    assert vista.clasificacion.confianza == 0.5
    assert (vista.clasificacion.modelo, vista.responsable) == (None, None)
    datos = conexion.execute(
        text("SELECT datos_extraidos FROM clasificacion WHERE id_pqrs = :id"), {"id": id_pqrs}
    ).scalar_one()
    assert datos == {"servicio": "resonancia"}


def test_obtener_y_existe_con_un_id_inexistente(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    assert repositorio.obtener(999_999) is None
    assert not repositorio.existe(999_999)
    assert repositorio.existe(_registrar(repositorio))


def test_el_radicado_es_unico(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    id_pqrs = _registrar(repositorio)
    with pytest.raises(IntegrityError, match="uq_pqrs_radicado"):
        conexion.execute(
            text(
                "INSERT INTO pqrs (radicado, id_peticionario, canal, fecha_radicacion,"
                " texto_original_cifrado, texto_enmascarado, tipo, nivel_riesgo, id_termino,"
                " fecha_vencimiento, estado, estado_ia)"
                " SELECT radicado, id_peticionario, canal, fecha_radicacion, texto_original_cifrado,"
                " texto_enmascarado, tipo, nivel_riesgo, id_termino, fecha_vencimiento, estado,"
                " estado_ia FROM pqrs WHERE id_pqrs = :id"
            ),
            {"id": id_pqrs},
        )


def test_listar_filtra_y_ordena_por_vencimiento(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    tarde = _registrar(
        repositorio, TipoPqrs.PETICION, NivelRiesgo.NO_APLICA, 1,
        datetime(2026, 11, 24, 23, 59, 59, tzinfo=ZONA_COLOMBIA), id_area=None,
    )
    temprano = _registrar(repositorio, vencimiento=datetime(2026, 10, 31, 16, tzinfo=ZONA_COLOMBIA))
    medio = _registrar(repositorio, estado=EstadoPqrs.REQUIERE_REVISION)

    assert [v.id for v in repositorio.listar(FiltroBandeja())] == [temprano, medio, tarde]
    assert [v.id for v in repositorio.listar(FiltroBandeja(tipo=TipoPqrs.PETICION))] == [tarde]
    assert [v.id for v in repositorio.listar(FiltroBandeja(id_area=4))] == [temprano, medio]
    revision = FiltroBandeja(estado=EstadoPqrs.REQUIERE_REVISION, id_area=4)
    assert [v.id for v in repositorio.listar(revision)] == [medio]


def test_auditoria_en_orden_cronologico(conexion: Connection) -> None:
    id_pqrs = _registrar(PqrsRepositoryPostgres(conexion))
    auditoria = AuditoriaRepositoryPostgres(conexion)
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.PERSONA, AccionAuditoria.REGISTRAR, id_usuario=1,
                        campo="estado", valor_nuevo="REGISTRADA")
    )
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.SISTEMA, AccionAuditoria.CALCULAR_VENCIMIENTO,
                        campo="fecha_vencimiento", valor_nuevo="2026-11-02T16:00:00-05:00",
                        motivo="Reclamo en salud, riesgo simple: 72 horas corridas")
    )

    eventos = auditoria.historial(id_pqrs)

    assert [(e.accion, e.origen, e.id_usuario) for e in eventos] == [
        (AccionAuditoria.REGISTRAR, OrigenEvento.PERSONA, 1),
        (AccionAuditoria.CALCULAR_VENCIMIENTO, OrigenEvento.SISTEMA, None),
    ]
    assert all(e.fecha is not None and e.id_evento is not None for e in eventos)
    assert eventos[1].motivo == "Reclamo en salud, riesgo simple: 72 horas corridas"
    assert auditoria.historial(999_999) == []


def test_terminos_vigentes_segun_la_fecha(conexion: Connection) -> None:
    configuracion = ConfiguracionRepositoryPostgres(conexion)

    assert [t.id for t in configuracion.terminos_vigentes(date(2026, 10, 31))] == list(range(1, 10))
    assert [t.id for t in configuracion.terminos_vigentes(date(2026, 6, 8))] == list(range(1, 9))
    assert configuracion.terminos_vigentes(date(2025, 12, 31)) == ()


def test_festivos_y_catalogo(conexion: Connection) -> None:
    configuracion = ConfiguracionRepositoryPostgres(conexion)

    festivos = configuracion.festivos(1)
    assert len(festivos) == 36 and date(2026, 11, 2) in festivos
    assert configuracion.festivos(99) == frozenset()

    catalogo = configuracion.catalogo()
    assert catalogo.tipos == tuple(TipoPqrs)
    assert [a.nombre for a in catalogo.areas][3] == "Autorizaciones"
    assert len(catalogo.atributos) == 7 and catalogo.atributos[1].nombre == "Oportunidad"
