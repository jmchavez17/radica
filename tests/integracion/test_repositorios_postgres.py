"""Repositorios de PostgreSQL contra una base temporal migrada.

Cada prueba trabaja dentro de una transacción que se deshace al final.
"""

from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from radica.adaptadores.salida.postgres.repositorios import (
    AuditoriaRepositoryPostgres,
    ConfiguracionRepositoryPostgres,
    PqrsRepositoryPostgres,
    comprobar_conexion,
)
from radica.aplicacion.puertos.clasificador import UsoIA
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
    ResultadoLlamadaIA,
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


# --- Sesión 4: lo que usan ClasificarPqrs, el trabajador y el reintento ---

def _uso(resultado: ResultadoLlamadaIA = ResultadoLlamadaIA.OK, intento: int = 1) -> UsoIA:
    return UsoIA("anthropic", "claude-haiku-5-5", 1200, 150, Decimal("0.000195"), 850, intento, resultado)


def test_obtener_para_clasificar(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    id_pqrs = _registrar(repositorio)

    datos = repositorio.obtener_para_clasificar(id_pqrs)

    assert datos is not None
    assert (datos.tipo, datos.nivel_riesgo, datos.id_atributo, datos.id_area) == (
        TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE, 2, 4,
    )
    assert datos.fecha_radicacion == RADICACION
    assert datos.fecha_vencimiento == datetime(2026, 11, 2, 16, tzinfo=ZONA_COLOMBIA)
    assert (datos.estado, datos.estado_ia, datos.paciente_menor) == (
        EstadoPqrs.REGISTRADA, EstadoIa.PENDIENTE, False,
    )
    assert datos.texto_enmascarado == "Mi teléfono es [TELEFONO_1]."
    assert datos.peticionario == _peticionario()
    assert repositorio.obtener_para_clasificar(999_999) is None


def test_pendientes_de_ia_de_la_mas_antigua_a_la_mas_nueva(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    primera, segunda, tercera = (_registrar(repositorio) for _ in range(3))
    repositorio.actualizar_estado(segunda, EstadoPqrs.CLASIFICADA, EstadoIa.COMPLETADA)
    # Las tres comparten fecha_creacion (misma transacción): desempata el id.

    assert repositorio.pendientes_de_ia(5) == [primera, tercera]
    assert repositorio.pendientes_de_ia() == [primera]


def test_aplicar_una_clasificacion_nueva(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    auditoria = AuditoriaRepositoryPostgres(conexion)
    id_pqrs = _registrar(repositorio)
    id_llamada = auditoria.registrar_llamada_ia(id_pqrs, _uso(), "clasif-v1.0")
    nueva = Clasificacion(
        OrigenClasificacion.IA, TipoPqrs.RECLAMO, 2, 4, NivelRiesgo.PRIORIZADO, 0.86,
        resumen="Paciente espera la autorización de una resonancia.", id_llamada_ia=id_llamada,
    )

    with pytest.raises(IntegrityError, match="uq_clasificacion_vigente"):
        with conexion.begin_nested():
            repositorio.guardar_clasificacion(id_pqrs, nueva)
    repositorio.retirar_clasificacion_vigente(id_pqrs)
    repositorio.guardar_clasificacion(id_pqrs, nueva)
    repositorio.actualizar_clasificacion(
        id_pqrs, TipoPqrs.RECLAMO, 2, NivelRiesgo.PRIORIZADO, 7,
        datetime(2026, 11, 1, 16, tzinfo=ZONA_COLOMBIA),
    )
    repositorio.actualizar_estado(id_pqrs, EstadoPqrs.CLASIFICADA, EstadoIa.COMPLETADA)

    vista = repositorio.obtener(id_pqrs)
    assert vista is not None and vista.clasificacion is not None
    assert (vista.nivel_riesgo, vista.termino.id, vista.estado, vista.estado_ia) == (
        NivelRiesgo.PRIORIZADO, 7, EstadoPqrs.CLASIFICADA, EstadoIa.COMPLETADA,
    )
    assert vista.fecha_vencimiento == datetime(2026, 11, 1, 16, tzinfo=ZONA_COLOMBIA)
    assert vista.clasificacion.origen is OrigenClasificacion.IA
    assert (vista.clasificacion.modelo, vista.clasificacion.version_instrucciones) == (
        "claude-haiku-5-5", "clasif-v1.0",
    )
    vigentes = conexion.execute(
        text("SELECT origen, vigente FROM clasificacion WHERE id_pqrs = :id ORDER BY id_clasificacion"),
        {"id": id_pqrs},
    ).all()
    assert [tuple(fila) for fila in vigentes] == [("REGLAS", False), ("IA", True)]


def test_marcar_pendiente_solo_si_no_cambio_antes(conexion: Connection) -> None:
    repositorio = PqrsRepositoryPostgres(conexion)
    id_pqrs = _registrar(repositorio)
    repositorio.actualizar_estado(id_pqrs, EstadoPqrs.REQUIERE_REVISION, EstadoIa.FALLIDA)

    assert not repositorio.marcar_pendiente(id_pqrs, EstadoIa.COMPLETADA)
    assert repositorio.marcar_pendiente(id_pqrs, EstadoIa.FALLIDA)
    assert not repositorio.marcar_pendiente(id_pqrs, EstadoIa.FALLIDA)
    datos = repositorio.obtener_para_clasificar(id_pqrs)
    assert datos is not None
    assert (datos.estado, datos.estado_ia) == (EstadoPqrs.REQUIERE_REVISION, EstadoIa.PENDIENTE)


def test_llamada_ia_guarda_solo_metadatos(conexion: Connection) -> None:
    id_pqrs = _registrar(PqrsRepositoryPostgres(conexion))
    auditoria = AuditoriaRepositoryPostgres(conexion)

    primero = auditoria.registrar_llamada_ia(id_pqrs, _uso(ResultadoLlamadaIA.TIMEOUT), "clasif-v1.0")
    segundo = auditoria.registrar_llamada_ia(id_pqrs, _uso(intento=2), "clasif-v1.0")

    assert segundo == primero + 1
    filas = conexion.execute(
        text("SELECT * FROM llamada_ia WHERE id_pqrs = :id ORDER BY id_llamada"), {"id": id_pqrs}
    ).mappings().all()
    assert set(filas[0]) == {
        "id_llamada", "id_pqrs", "operacion", "proveedor", "modelo", "version_instrucciones",
        "intento", "resultado", "tokens_entrada", "tokens_salida", "costo_usd", "latencia_ms", "fecha",
    }
    assert [(f["operacion"], f["intento"], f["resultado"]) for f in filas] == [
        ("CLASIFICAR", 1, "TIMEOUT"), ("CLASIFICAR", 2, "OK"),
    ]
    assert (filas[1]["tokens_entrada"], filas[1]["tokens_salida"], filas[1]["costo_usd"]) == (
        1200, 150, Decimal("0.000195"),
    )


def test_el_historial_trae_modelo_y_version_en_los_eventos_de_la_ia(conexion: Connection) -> None:
    id_pqrs = _registrar(PqrsRepositoryPostgres(conexion))
    auditoria = AuditoriaRepositoryPostgres(conexion)
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.SISTEMA, AccionAuditoria.CLASIFICAR_REGLAS,
                        campo="tipo", valor_nuevo="RECLAMO")
    )
    auditoria.registrar_llamada_ia(id_pqrs, _uso(ResultadoLlamadaIA.TIMEOUT), "clasif-v0.9")
    auditoria.registrar_llamada_ia(id_pqrs, _uso(intento=2), "clasif-v1.0")
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.IA, AccionAuditoria.CLASIFICAR_IA,
                        campo="nivel_riesgo", valor_anterior="SIMPLE", valor_nuevo="PRIORIZADO")
    )
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.SISTEMA, AccionAuditoria.CALCULAR_VENCIMIENTO,
                        campo="fecha_vencimiento", valor_nuevo="2026-11-01T16:00:00-05:00")
    )

    eventos = auditoria.historial(id_pqrs)

    assert [(e.accion, e.modelo, e.version_instrucciones) for e in eventos] == [
        (AccionAuditoria.CLASIFICAR_REGLAS, None, None),
        (AccionAuditoria.CLASIFICAR_IA, "claude-haiku-5-5", "clasif-v1.0"),
        (AccionAuditoria.CALCULAR_VENCIMIENTO, None, None),
    ]


def test_sin_llamada_ok_en_la_transaccion_el_evento_no_inventa_modelo(conexion: Connection) -> None:
    id_pqrs = _registrar(PqrsRepositoryPostgres(conexion))
    auditoria = AuditoriaRepositoryPostgres(conexion)
    auditoria.registrar_llamada_ia(id_pqrs, _uso(ResultadoLlamadaIA.SALIDA_INVALIDA), "clasif-v1.0")
    auditoria.registrar(
        EventoAuditoria(id_pqrs, OrigenEvento.SISTEMA, AccionAuditoria.SUGERENCIA_IA_NO_APLICADA,
                        campo="estado", valor_nuevo="REQUIERE_REVISION")
    )

    (evento,) = auditoria.historial(id_pqrs)
    assert (evento.modelo, evento.version_instrucciones) == (None, None)
