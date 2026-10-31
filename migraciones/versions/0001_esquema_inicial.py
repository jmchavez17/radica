"""Esquema inicial: las 13 tablas del modelo de datos v1.1.

Transcribe docs/modelo-datos.md, incluido el cambio aprobado el 31-oct-2026 de
VARCHAR(20) a VARCHAR(25) en las columnas de tipo de PQRS. Convenciones:
llaves con identidad generada (BY DEFAULT, para que las semillas lleven ids
fijos), llaves foráneas con ON DELETE RESTRICT, columnas NOT NULL salvo las que
el diccionario marca como NULL y valores cerrados con CHECK. Los valores se
escriben aquí y no se importan del código, para que esta migración no cambie
si cambian las enumeraciones del dominio.

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_PQRS = ("PETICION", "QUEJA", "RECLAMO", "SUGERENCIA", "SOLICITUD_INFORMACION", "CONSULTA")
NIVELES_RIESGO = ("NO_APLICA", "SIMPLE", "PRIORIZADO", "VITAL")
CANALES = ("DIME", "CARTA", "CORREO", "WEB", "VERBAL", "BUZON", "APLICATIVO_EPS")
ESTADOS_PQRS = (
    "REGISTRADA",
    "REQUIERE_REVISION",
    "CLASIFICADA",
    "ASIGNADA",
    "EN_RESPUESTA",
    "RESPONDIDA",
    "CERRADA",
)
ESTADOS_IA = ("PENDIENTE", "COMPLETADA", "FALLIDA", "OMITIDA")
RESULTADOS_LLAMADA_IA = (
    "OK",
    "TIMEOUT",
    "LIMITE_CUOTA",
    "ERROR_PROVEEDOR",
    "CREDENCIAL_INVALIDA",
    "SALIDA_INVALIDA",
)

TIPO_PQRS = sa.String(25)


def _llave(columna: str, tipo: type[sa.types.TypeEngine] = sa.BigInteger) -> sa.Column:
    return sa.Column(columna, tipo, sa.Identity(always=False), primary_key=True)


def _fk(tabla: str, columna: str, destino: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [columna], [destino], name=f"fk_{tabla}_{columna}", ondelete="RESTRICT"
    )


def _en(tabla: str, columna: str, valores: Sequence[str]) -> sa.CheckConstraint:
    lista = ", ".join(f"'{valor}'" for valor in valores)
    return sa.CheckConstraint(f"{columna} IN ({lista})", name=f"ck_{tabla}_{columna}")


def _ahora(columna: str) -> sa.Column:
    return sa.Column(
        columna, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "calendario",
        _llave("id_calendario", sa.Integer),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.UniqueConstraint("nombre", name="uq_calendario_nombre"),
    )

    op.create_table(
        "festivo",
        sa.Column("id_calendario", sa.Integer, nullable=False),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column("descripcion", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id_calendario", "fecha"),
        _fk("festivo", "id_calendario", "calendario.id_calendario"),
    )

    op.create_table(
        "termino_legal",
        _llave("id_termino", sa.Integer),
        sa.Column("regimen", sa.String(10), nullable=False),
        sa.Column("tipo_pqrs", TIPO_PQRS, nullable=False),
        sa.Column("nivel_riesgo", sa.String(12), nullable=False),
        sa.Column("poblacion", sa.String(10), nullable=False),
        sa.Column("valor", sa.SmallInteger, nullable=False),
        sa.Column("unidad", sa.String(15), nullable=False),
        sa.Column("id_calendario", sa.Integer, nullable=True),
        sa.Column("fuente_normativa", sa.String(150), nullable=False),
        sa.Column("vigente_desde", sa.Date, nullable=False),
        sa.Column("vigente_hasta", sa.Date, nullable=True),
        _fk("termino_legal", "id_calendario", "calendario.id_calendario"),
        _en("termino_legal", "regimen", ("GENERAL", "SALUD")),
        _en("termino_legal", "tipo_pqrs", TIPOS_PQRS),
        _en("termino_legal", "nivel_riesgo", NIVELES_RIESGO),
        _en("termino_legal", "poblacion", ("TODAS", "MENOR")),
        sa.CheckConstraint("valor > 0", name="ck_termino_legal_valor"),
        _en("termino_legal", "unidad", ("DIAS_HABILES", "HORAS_CORRIDAS")),
        sa.CheckConstraint(
            "(unidad = 'DIAS_HABILES' AND id_calendario IS NOT NULL)"
            " OR (unidad = 'HORAS_CORRIDAS' AND id_calendario IS NULL)",
            name="ck_termino_legal_calendario_segun_unidad",
        ),
    )

    op.create_table(
        "area",
        _llave("id_area", sa.Integer),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("correo_notificacion", sa.String(120), nullable=False),
        sa.Column("activa", sa.Boolean, nullable=False),
        sa.UniqueConstraint("nombre", name="uq_area_nombre"),
    )

    op.create_table(
        "atributo_calidad",
        _llave("id_atributo", sa.Integer),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("definicion", sa.Text, nullable=False),
        sa.Column("tipo_sugerido", TIPO_PQRS, nullable=False),
        sa.Column("id_area_sugerida", sa.Integer, nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.UniqueConstraint("nombre", name="uq_atributo_calidad_nombre"),
        _fk("atributo_calidad", "id_area_sugerida", "area.id_area"),
        _en("atributo_calidad", "tipo_sugerido", TIPOS_PQRS),
    )

    op.create_table(
        "usuario",
        _llave("id_usuario"),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("correo", sa.String(120), nullable=False),
        sa.Column("hash_contrasena", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(15), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        _ahora("fecha_creacion"),
        sa.UniqueConstraint("correo", name="uq_usuario_correo"),
        _en("usuario", "rol", ("FUNCIONARIO", "COORDINADOR", "ADMIN")),
    )

    op.create_table(
        "peticionario",
        _llave("id_peticionario"),
        sa.Column("documento_hash", sa.CHAR(64), nullable=False),
        sa.Column("nombre_cifrado", sa.LargeBinary, nullable=False),
        sa.Column("contacto_cifrado", sa.LargeBinary, nullable=False),
        _ahora("fecha_creacion"),
        sa.UniqueConstraint("documento_hash", name="uq_peticionario_documento_hash"),
    )

    op.create_table(
        "pqrs",
        _llave("id_pqrs"),
        sa.Column("radicado", sa.String(20), nullable=False),
        sa.Column("id_peticionario", sa.BigInteger, nullable=False),
        sa.Column("canal", sa.String(20), nullable=False),
        sa.Column("sede", sa.String(60), nullable=True),
        sa.Column("fecha_radicacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("texto_original_cifrado", sa.LargeBinary, nullable=False),
        sa.Column("texto_enmascarado", sa.Text, nullable=False),
        sa.Column("tipo", TIPO_PQRS, nullable=False),
        sa.Column("id_atributo", sa.Integer, nullable=True),
        sa.Column("nivel_riesgo", sa.String(12), nullable=False),
        sa.Column("paciente_menor", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("id_termino", sa.Integer, nullable=False),
        sa.Column("fecha_vencimiento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prorrogada", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("estado_ia", sa.String(12), nullable=False),
        sa.Column("id_area", sa.Integer, nullable=True),
        sa.Column("id_responsable", sa.BigInteger, nullable=True),
        sa.Column("id_pqrs_relacionada", sa.BigInteger, nullable=True),
        sa.Column("fecha_respuesta", sa.DateTime(timezone=True), nullable=True),
        _ahora("fecha_creacion"),
        sa.UniqueConstraint("radicado", name="uq_pqrs_radicado"),
        _fk("pqrs", "id_peticionario", "peticionario.id_peticionario"),
        _fk("pqrs", "id_atributo", "atributo_calidad.id_atributo"),
        _fk("pqrs", "id_termino", "termino_legal.id_termino"),
        _fk("pqrs", "id_area", "area.id_area"),
        _fk("pqrs", "id_responsable", "usuario.id_usuario"),
        _fk("pqrs", "id_pqrs_relacionada", "pqrs.id_pqrs"),
        _en("pqrs", "canal", CANALES),
        _en("pqrs", "tipo", TIPOS_PQRS),
        _en("pqrs", "nivel_riesgo", NIVELES_RIESGO),
        _en("pqrs", "estado", ESTADOS_PQRS),
        _en("pqrs", "estado_ia", ESTADOS_IA),
    )
    op.create_index(
        "ix_pqrs_fecha_vencimiento_abiertas",
        "pqrs",
        ["fecha_vencimiento"],
        postgresql_where=sa.text("estado NOT IN ('RESPONDIDA', 'CERRADA')"),
    )
    op.create_index("ix_pqrs_estado_ia", "pqrs", ["estado_ia"])
    op.create_index("ix_pqrs_id_area", "pqrs", ["id_area"])

    op.create_table(
        "llamada_ia",
        _llave("id_llamada"),
        sa.Column("id_pqrs", sa.BigInteger, nullable=False),
        sa.Column("operacion", sa.String(12), nullable=False),
        sa.Column("proveedor", sa.String(30), nullable=False),
        sa.Column("modelo", sa.String(60), nullable=False),
        sa.Column("version_instrucciones", sa.String(20), nullable=False),
        sa.Column("intento", sa.SmallInteger, nullable=False),
        sa.Column("resultado", sa.String(25), nullable=False),
        sa.Column("tokens_entrada", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_salida", sa.Integer, nullable=False, server_default="0"),
        sa.Column("costo_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("latencia_ms", sa.Integer, nullable=False),
        _ahora("fecha"),
        _fk("llamada_ia", "id_pqrs", "pqrs.id_pqrs"),
        _en("llamada_ia", "operacion", ("CLASIFICAR", "REDACTAR")),
        _en("llamada_ia", "resultado", RESULTADOS_LLAMADA_IA),
    )

    op.create_table(
        "clasificacion",
        _llave("id_clasificacion"),
        sa.Column("id_pqrs", sa.BigInteger, nullable=False),
        sa.Column("id_llamada_ia", sa.BigInteger, nullable=True),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("tipo", TIPO_PQRS, nullable=False),
        sa.Column("id_atributo", sa.Integer, nullable=True),
        sa.Column("id_area", sa.Integer, nullable=True),
        sa.Column("nivel_riesgo", sa.String(12), nullable=False),
        sa.Column("confianza", sa.Numeric(4, 3), nullable=False),
        sa.Column("resumen", sa.String(300), nullable=True),
        sa.Column("datos_extraidos", postgresql.JSONB, nullable=True),
        sa.Column("vigente", sa.Boolean, nullable=False),
        _ahora("fecha"),
        _fk("clasificacion", "id_pqrs", "pqrs.id_pqrs"),
        _fk("clasificacion", "id_llamada_ia", "llamada_ia.id_llamada"),
        _fk("clasificacion", "id_atributo", "atributo_calidad.id_atributo"),
        _fk("clasificacion", "id_area", "area.id_area"),
        _en("clasificacion", "origen", ("REGLAS", "IA", "PERSONA")),
        _en("clasificacion", "tipo", TIPOS_PQRS),
        _en("clasificacion", "nivel_riesgo", NIVELES_RIESGO),
        sa.CheckConstraint("confianza BETWEEN 0 AND 1", name="ck_clasificacion_confianza"),
    )
    op.create_index("ix_clasificacion_id_pqrs_vigente", "clasificacion", ["id_pqrs", "vigente"])
    op.create_index(
        "uq_clasificacion_vigente_por_pqrs",
        "clasificacion",
        ["id_pqrs"],
        unique=True,
        postgresql_where=sa.text("vigente"),
    )

    op.create_table(
        "borrador",
        _llave("id_borrador"),
        sa.Column("id_pqrs", sa.BigInteger, nullable=False),
        sa.Column("id_llamada_ia", sa.BigInteger, nullable=True),
        sa.Column("id_aprobador", sa.BigInteger, nullable=True),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("contenido", sa.Text, nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("editado", sa.Boolean, nullable=False, server_default=sa.false()),
        _ahora("fecha_creacion"),
        sa.Column("fecha_aprobacion", sa.DateTime(timezone=True), nullable=True),
        _fk("borrador", "id_pqrs", "pqrs.id_pqrs"),
        _fk("borrador", "id_llamada_ia", "llamada_ia.id_llamada"),
        _fk("borrador", "id_aprobador", "usuario.id_usuario"),
        _en("borrador", "origen", ("IA", "PLANTILLA")),
        _en("borrador", "estado", ("GENERADO", "APROBADO", "DESCARTADO")),
    )
    op.create_index(
        "uq_borrador_aprobado_por_pqrs",
        "borrador",
        ["id_pqrs"],
        unique=True,
        postgresql_where=sa.text("estado = 'APROBADO'"),
    )

    op.create_table(
        "auditoria",
        _llave("id_evento"),
        sa.Column("id_pqrs", sa.BigInteger, nullable=False),
        sa.Column("id_usuario", sa.BigInteger, nullable=True),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("accion", sa.String(40), nullable=False),
        sa.Column("campo", sa.String(40), nullable=True),
        sa.Column("valor_anterior", sa.Text, nullable=True),
        sa.Column("valor_nuevo", sa.Text, nullable=True),
        sa.Column("motivo", sa.String(300), nullable=True),
        _ahora("fecha"),
        _fk("auditoria", "id_pqrs", "pqrs.id_pqrs"),
        _fk("auditoria", "id_usuario", "usuario.id_usuario"),
        _en("auditoria", "origen", ("PERSONA", "IA", "SISTEMA")),
    )
    op.create_index("ix_auditoria_id_pqrs_fecha", "auditoria", ["id_pqrs", "fecha"])

    # Solo inserción (contexto.md 4.12): equivale al REVOKE UPDATE, DELETE de la
    # Entrega 2 mientras la aplicación y las migraciones usan el mismo usuario.
    # TRUNCATE también se bloquea porque el disparador de filas no lo detiene.
    op.execute(
        """
        CREATE FUNCTION auditoria_solo_insercion() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla auditoria es de solo inserción: % no está permitido', TG_OP;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_auditoria_solo_insercion
        BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_solo_insercion()
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_auditoria_sin_truncate
        BEFORE TRUNCATE ON auditoria
        FOR EACH STATEMENT EXECUTE FUNCTION auditoria_solo_insercion()
        """
    )

    op.create_table(
        "notificacion",
        _llave("id_notificacion"),
        sa.Column("id_pqrs", sa.BigInteger, nullable=False),
        sa.Column("tipo", sa.String(15), nullable=False),
        sa.Column("destinatario", sa.String(120), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("intentos", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("fecha_programada", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
        _fk("notificacion", "id_pqrs", "pqrs.id_pqrs"),
        _en("notificacion", "tipo", ("ASIGNACION", "RECORDATORIO", "VENCIDA", "RIESGO_VITAL")),
        _en("notificacion", "estado", ("PENDIENTE", "ENVIADA", "FALLIDA")),
    )


def downgrade() -> None:
    for tabla in (
        "notificacion",
        "auditoria",
        "borrador",
        "clasificacion",
        "llamada_ia",
        "pqrs",
        "peticionario",
        "usuario",
        "atributo_calidad",
        "area",
        "termino_legal",
        "festivo",
        "calendario",
    ):
        op.drop_table(tabla)
    op.execute("DROP FUNCTION auditoria_solo_insercion()")
