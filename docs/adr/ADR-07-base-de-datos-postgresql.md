# ADR-07 · Base de datos: PostgreSQL 16

Fecha: 14-nov-2026. Detalla la parte de base de datos de [ADR-06](ADR-06-tecnologias.md); no la reemplaza.

## Estado

**Aceptada** (14-nov-2026).

## Contexto

ADR-06 eligió PostgreSQL 16 con una sola razón, «el equipo ya trabaja con PostgreSQL», que no se puede comprobar en el repositorio. El curso usa MySQL 8. Este ADR deja escritas las razones que sí se ven en el código y en las migraciones, para que cualquiera pueda verificarlas, y lo que costaría cambiar de motor.

Radica tiene dos procesos que escriben en la misma base: la API y el trabajador, en contenedores distintos (`docker-compose.yml:45` y `:63`). El esquema lo controlan las migraciones de Alembic (`docs/contexto.md` §6, regla 5).

## Decisión

PostgreSQL 16, con la imagen `postgres:16.15-trixie` (`docker-compose.yml:28`). La aplicación usa SQL parametrizado con SQLAlchemy 2.1 y psycopg 3 (`pyproject.toml`). Las pruebas de integración exigen la versión 16 (`tests/integracion/test_migracion.py:126`).

Razones. Cada una es algo que Radica ya usa de PostgreSQL:

| # | Qué usa Radica | Para qué | Dónde se comprueba |
| --- | --- | --- | --- |
| 1 | `SELECT … FOR UPDATE SKIP LOCKED` | La cola de clasificación sin broker (ADR-04): dos trabajadores no toman la misma PQRS | `src/radica/adaptadores/salida/postgres/repositorios.py:245-251`; `tests/integracion/test_trabajador.py:134` |
| 2 | Función en PL/pgSQL con disparadores de fila (`UPDATE`, `DELETE`) y de sentencia (`TRUNCATE`) | La tabla `auditoria` es de solo inserción (`docs/contexto.md` §4.12) | `migraciones/versions/0001_esquema_inicial.py:306-332`; `tests/integracion/test_migracion.py:163` |
| 3 | Índices únicos parciales | La base garantiza una sola clasificación vigente por PQRS y un solo borrador aprobado; otro índice parcial indexa el vencimiento solo de las PQRS abiertas | `0001_esquema_inicial.py:200-205`, `254-260` y `280-286` |
| 4 | `INSERT … ON CONFLICT DO NOTHING RETURNING` y `UPDATE … RETURNING` | Reutilizar el peticionario por el HMAC de su documento, y «comparar y cambiar» el estado de IA en una sola sentencia cuando llegan dos reintentos a la vez | `repositorios.py:145` y `336` |
| 5 | Secuencias: `nextval(pg_get_serial_sequence('pqrs', 'id_pqrs'))` | Reservar el id antes de insertar, para armar el radicado con él | `repositorios.py:130-133`; `src/radica/aplicacion/casos_de_uso/registrar_pqrs.py:121` |
| 6 | `JSONB` | `clasificacion.datos_extraidos`, los datos clave que devuelve la IA | `0001_esquema_inicial.py:241`; `repositorios.py:193` |
| 7 | Un servidor con varias conexiones que escriben a la vez | La API y el trabajador escriben en paralelo desde dos contenedores | `docker-compose.yml:45-80` |

## Alternativas

Las columnas de MySQL 8 y SQLite resumen lo que dicen sus manuales; no se probaron en este repositorio.

| Qué usa Radica | MySQL 8 | SQLite |
| --- | --- | --- |
| 1. `FOR UPDATE SKIP LOCKED` | Lo tiene | No tiene `SELECT … FOR UPDATE` y admite un solo escritor a la vez |
| 2. Disparador de sentencia para `TRUNCATE` | Solo disparadores de fila, y `TRUNCATE` no los activa | No tiene `TRUNCATE`; un disparador de fila sobre `DELETE` bastaría |
| 3. Índices únicos parciales | No los tiene | Los tiene |
| 4. `ON CONFLICT` y `RETURNING` | No los tiene (usa `INSERT IGNORE` u `ON DUPLICATE KEY UPDATE`) | Los tiene |
| 5. Secuencias | No las tiene (`AUTO_INCREMENT` asigna el id al insertar) | No las tiene |
| 6. `JSONB` | Tiene `JSON`, con otra sintaxis | Guarda el JSON como texto, con otra sintaxis |
| 7. Varios escritores | Sí, es un servidor | Un archivo con un solo escritor a la vez |

1. **MySQL 8, la base de datos del curso.** A favor: los ejemplos de clase servirían tal cual y la cola de ADR-04 funcionaría igual. En contra: habría que llevar al código las reglas que hoy cumplen los índices parciales (una clasificación vigente, un borrador aprobado), reescribir las consultas con `ON CONFLICT` y `RETURNING` como una escritura y una lectura aparte, cambiar la reserva del id para el radicado y bloquear `TRUNCATE` sobre `auditoria` con permisos en vez de un disparador.
2. **SQLite.** A favor: no necesita servidor, lo que simplifica las pruebas. En contra: la API y el trabajador, en contenedores distintos, tendrían que compartir un archivo por un volumen y no podrían escribir a la vez; sin `FOR UPDATE` la cola de ADR-04 habría que rediseñarla, y tampoco tiene secuencias.

## Consecuencias

Ventajas:

- La base cumple reglas que de otro modo tendría que cumplir el código: una sola clasificación vigente, un solo borrador aprobado y la auditoría de solo inserción.
- La cola de clasificación no necesita más infraestructura (ADR-04).
- Las pruebas de integración corren contra la misma versión que el contenedor `db` (`tests/integracion/test_migracion.py:126`).

Costos:

- El SQL es específico de PostgreSQL: la migración inicial importa `sqlalchemy.dialects.postgresql` (`0001_esquema_inicial.py:20`) y `repositorios.py` usa su sintaxis. Cambiar de motor obliga a reescribir los dos.
- Las pruebas de integración necesitan un PostgreSQL levantado; sin `RADICA_DB_URL` se omiten (`tests/integracion/conftest.py:40`).
- Se aparta de MySQL 8, la base de datos del curso.
