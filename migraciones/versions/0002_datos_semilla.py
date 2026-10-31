"""Datos semilla del modelo v1.1 (docs/modelo-datos.md, sección 2).

Todo es sintético salvo los festivos y los términos legales. Las filas llevan
ids fijos; al final se ajusta cada secuencia de identidad para que los
registros nuevos continúen después de ellos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CALENDARIO_COLOMBIA = 1

# Fuente: Calendario de Colombia, «solo feriados» 2026 y 2027, consultado el 31-oct-2026.
FESTIVOS = (
    (date(2026, 1, 1), "Año Nuevo"),
    (date(2026, 1, 12), "Día de los Reyes Magos"),
    (date(2026, 3, 23), "Día de San José"),
    (date(2026, 4, 2), "Jueves Santo"),
    (date(2026, 4, 3), "Viernes Santo"),
    (date(2026, 5, 1), "Día del Trabajo"),
    (date(2026, 5, 18), "Ascensión del Señor"),
    (date(2026, 6, 8), "Corpus Christi"),
    (date(2026, 6, 15), "Sagrado Corazón"),
    (date(2026, 6, 29), "San Pedro y San Pablo"),
    (date(2026, 7, 20), "Día de la Independencia"),
    (date(2026, 8, 7), "Batalla de Boyacá"),
    (date(2026, 8, 17), "Asunción de la Virgen"),
    (date(2026, 10, 12), "Día de la Raza"),
    (date(2026, 11, 2), "Todos los Santos"),
    (date(2026, 11, 16), "Independencia de Cartagena"),
    (date(2026, 12, 8), "Inmaculada Concepción"),
    (date(2026, 12, 25), "Navidad"),
    (date(2027, 1, 1), "Año Nuevo"),
    (date(2027, 1, 11), "Día de los Reyes Magos"),
    (date(2027, 3, 22), "Día de San José"),
    (date(2027, 3, 25), "Jueves Santo"),
    (date(2027, 3, 26), "Viernes Santo"),
    (date(2027, 5, 1), "Día del Trabajo"),
    (date(2027, 5, 10), "Ascensión del Señor"),
    (date(2027, 5, 31), "Corpus Christi"),
    (date(2027, 6, 7), "Sagrado Corazón"),
    (date(2027, 7, 5), "San Pedro y San Pablo"),
    (date(2027, 7, 20), "Día de la Independencia"),
    (date(2027, 8, 7), "Batalla de Boyacá"),
    (date(2027, 8, 16), "Asunción de la Virgen"),
    (date(2027, 10, 18), "Día de la Raza"),
    (date(2027, 11, 1), "Todos los Santos"),
    (date(2027, 11, 15), "Independencia de Cartagena"),
    (date(2027, 12, 8), "Inmaculada Concepción"),
    (date(2027, 12, 25), "Navidad"),
)

LEY_1755 = "Ley 1755 de 2015, art. 14"
CIRCULAR_2023 = "Supersalud, Circular Externa 2023151000000010-5"
INICIO_TABLA = date(2026, 1, 1)  # SUPUESTO: inicio de la tabla en el sistema, no expedición de la norma

# (id, regimen, tipo_pqrs, nivel_riesgo, poblacion, valor, unidad, id_calendario, fuente, vigente_desde)
TERMINOS = (
    (1, "GENERAL", "PETICION", "NO_APLICA", "TODAS", 15, "DIAS_HABILES", CALENDARIO_COLOMBIA,
     LEY_1755, INICIO_TABLA),
    (2, "GENERAL", "SOLICITUD_INFORMACION", "NO_APLICA", "TODAS", 10, "DIAS_HABILES",
     CALENDARIO_COLOMBIA, LEY_1755, INICIO_TABLA),
    (3, "GENERAL", "CONSULTA", "NO_APLICA", "TODAS", 30, "DIAS_HABILES", CALENDARIO_COLOMBIA,
     LEY_1755, INICIO_TABLA),
    (4, "GENERAL", "QUEJA", "NO_APLICA", "TODAS", 15, "DIAS_HABILES", CALENDARIO_COLOMBIA,
     "Ley 1755 de 2015, art. 14; entrevista V1 (confirmar con jurídica)", INICIO_TABLA),
    (5, "GENERAL", "SUGERENCIA", "NO_APLICA", "TODAS", 15, "DIAS_HABILES", CALENDARIO_COLOMBIA,
     "Ley 1755 de 2015, art. 14 (confirmar con jurídica)", INICIO_TABLA),
    (6, "SALUD", "RECLAMO", "SIMPLE", "TODAS", 72, "HORAS_CORRIDAS", None,
     CIRCULAR_2023, INICIO_TABLA),
    (7, "SALUD", "RECLAMO", "PRIORIZADO", "TODAS", 48, "HORAS_CORRIDAS", None,
     CIRCULAR_2023, INICIO_TABLA),
    (8, "SALUD", "RECLAMO", "VITAL", "TODAS", 24, "HORAS_CORRIDAS", None,
     CIRCULAR_2023, INICIO_TABLA),
    # 2026-06-09: publicación de la Circular 2026151000000007-5 en el Diario Oficial 53.517.
    (9, "SALUD", "RECLAMO", "VITAL", "MENOR", 8, "HORAS_CORRIDAS", None,
     "Supersalud, Circular Externa 2026151000000007-5", date(2026, 6, 9)),
)

# Sintéticas: correos en el dominio reservado .test.
AREAS = (
    (1, "Atención al usuario", "atencion@radica.test"),
    (2, "Citas", "citas@radica.test"),
    (3, "Archivo clínico", "archivo@radica.test"),
    (4, "Autorizaciones", "autorizaciones@radica.test"),
    (5, "Facturación", "facturacion@radica.test"),
    (6, "Farmacia", "farmacia@radica.test"),
    (7, "Servicios asistenciales", "asistencial@radica.test"),
)

# Sintéticos: el catálogo real lo entrega la IPS en V3.
# (id, nombre, definicion, tipo_sugerido, id_area_sugerida)
ATRIBUTOS = (
    (1, "Calidad humana",
     "Trato del personal hacia el usuario: respeto, amabilidad y comunicación", "QUEJA", 1),
    (2, "Oportunidad",
     "Demora en obtener una cita, un examen, una autorización o un servicio", "RECLAMO", 4),
    (3, "Accesibilidad",
     "Barreras para acceder al servicio: horarios, canales, trámites o ubicación", "RECLAMO", 1),
    (4, "Seguridad del paciente",
     "Hechos que pusieron o pueden poner en riesgo la salud del usuario", "RECLAMO", 7),
    (5, "Medicamentos",
     "Entrega incompleta, tardía o equivocada de medicamentos", "RECLAMO", 6),
    (6, "Facturación y cobros",
     "Cobros, copagos o cuotas que el usuario considera indebidos", "RECLAMO", 5),
    (7, "Información y documentos",
     "Solicitudes de copias, certificados o información del servicio", "SOLICITUD_INFORMACION", 3),
)

# Actor de las acciones de persona mientras no haya autenticación (M5).
# «!» no es un hash válido: no hay contraseña con la que se pueda iniciar sesión.
USUARIO_SEMILLA = {
    "id_usuario": 1,
    "nombre": "Funcionario Sintético",
    "correo": "funcionario@radica.test",
    "hash_contrasena": "!",
    "rol": "FUNCIONARIO",
    "activo": True,
}

# Columnas con tipo para que `alembic upgrade --sql` pueda escribir los valores.
calendario = sa.table(
    "calendario",
    sa.column("id_calendario", sa.Integer),
    sa.column("nombre", sa.String),
    sa.column("activo", sa.Boolean),
)
festivo = sa.table(
    "festivo",
    sa.column("id_calendario", sa.Integer),
    sa.column("fecha", sa.Date),
    sa.column("descripcion", sa.String),
)
termino_legal = sa.table(
    "termino_legal",
    sa.column("id_termino", sa.Integer),
    sa.column("regimen", sa.String),
    sa.column("tipo_pqrs", sa.String),
    sa.column("nivel_riesgo", sa.String),
    sa.column("poblacion", sa.String),
    sa.column("valor", sa.SmallInteger),
    sa.column("unidad", sa.String),
    sa.column("id_calendario", sa.Integer),
    sa.column("fuente_normativa", sa.String),
    sa.column("vigente_desde", sa.Date),
)
area = sa.table(
    "area",
    sa.column("id_area", sa.Integer),
    sa.column("nombre", sa.String),
    sa.column("correo_notificacion", sa.String),
    sa.column("activa", sa.Boolean),
)
atributo_calidad = sa.table(
    "atributo_calidad",
    sa.column("id_atributo", sa.Integer),
    sa.column("nombre", sa.String),
    sa.column("definicion", sa.Text),
    sa.column("tipo_sugerido", sa.String),
    sa.column("id_area_sugerida", sa.Integer),
    sa.column("activo", sa.Boolean),
)
usuario = sa.table(
    "usuario",
    sa.column("id_usuario", sa.BigInteger),
    sa.column("nombre", sa.String),
    sa.column("correo", sa.String),
    sa.column("hash_contrasena", sa.String),
    sa.column("rol", sa.String),
    sa.column("activo", sa.Boolean),
)

# Tablas con ids fijos en las semillas: (tabla, columna de identidad).
IDENTIDADES = (
    ("calendario", "id_calendario"),
    ("termino_legal", "id_termino"),
    ("area", "id_area"),
    ("atributo_calidad", "id_atributo"),
    ("usuario", "id_usuario"),
)


def upgrade() -> None:
    op.bulk_insert(
        calendario,
        [{"id_calendario": CALENDARIO_COLOMBIA, "nombre": "Colombia nacional", "activo": True}],
    )
    op.bulk_insert(
        festivo,
        [
            {"id_calendario": CALENDARIO_COLOMBIA, "fecha": fecha, "descripcion": descripcion}
            for fecha, descripcion in FESTIVOS
        ],
    )
    op.bulk_insert(
        termino_legal,
        [
            {
                "id_termino": id_termino,
                "regimen": regimen,
                "tipo_pqrs": tipo,
                "nivel_riesgo": nivel,
                "poblacion": poblacion,
                "valor": valor,
                "unidad": unidad,
                "id_calendario": id_calendario,
                "fuente_normativa": fuente,
                "vigente_desde": desde,
            }
            for (id_termino, regimen, tipo, nivel, poblacion, valor, unidad, id_calendario,
                 fuente, desde) in TERMINOS
        ],
    )
    op.bulk_insert(
        area,
        [
            {"id_area": id_area, "nombre": nombre, "correo_notificacion": correo, "activa": True}
            for id_area, nombre, correo in AREAS
        ],
    )
    op.bulk_insert(
        atributo_calidad,
        [
            {
                "id_atributo": id_atributo,
                "nombre": nombre,
                "definicion": definicion,
                "tipo_sugerido": tipo,
                "id_area_sugerida": id_area,
                "activo": True,
            }
            for id_atributo, nombre, definicion, tipo, id_area in ATRIBUTOS
        ],
    )
    op.bulk_insert(usuario, [USUARIO_SEMILLA])

    for tabla, columna in IDENTIDADES:
        op.execute(
            f"SELECT setval(pg_get_serial_sequence('{tabla}', '{columna}'),"
            f" (SELECT max({columna}) FROM {tabla}))"
        )


def downgrade() -> None:
    op.execute(usuario.delete().where(usuario.c.id_usuario == USUARIO_SEMILLA["id_usuario"]))
    op.execute(
        atributo_calidad.delete().where(
            atributo_calidad.c.id_atributo.in_([fila[0] for fila in ATRIBUTOS])
        )
    )
    op.execute(area.delete().where(area.c.id_area.in_([fila[0] for fila in AREAS])))
    op.execute(
        termino_legal.delete().where(
            termino_legal.c.id_termino.in_([fila[0] for fila in TERMINOS])
        )
    )
    op.execute(
        festivo.delete().where(
            festivo.c.id_calendario == CALENDARIO_COLOMBIA,
            festivo.c.fecha.in_([fecha for fecha, _ in FESTIVOS]),
        )
    )
    op.execute(calendario.delete().where(calendario.c.id_calendario == CALENDARIO_COLOMBIA))
