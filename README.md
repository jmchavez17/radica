# Radica

Asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para oficinas de atención al usuario que deben responder dentro de términos legales. Proyecto del Diplomado en Ingeniería de Software asistida por Inteligencia Artificial de la Universidad Santiago de Cali, por Jose Miguel Chávez Figueroa e Isabella Castaño Muñoz. Todo el proyecto usa datos sintéticos.

## Estado actual

Hoy contiene:

- El registro de PQRS por API: cifrado AES-256-GCM de los datos del peticionario con HMAC del documento, enmascaramiento por reglas, clasificación provisional, cálculo del vencimiento y auditoría, todo en una sola transacción.
- La consulta de una PQRS, la bandeja con semáforo, el historial de auditoría y la tabla de términos vigente.
- Las reglas puras del dominio: selección del término, CalculadoraDePlazos y semáforo.
- El puerto `ClasificadorPqrs` y su contrato. La clasificación provisional la hace `ClasificadorPalabrasClave`, con su diccionario versionado en `src/radica/adaptadores/salida/palabras_clave/diccionario.json`.
- 12 PQRS sintéticas para la demostración en `datos/sinteticos/demo.json`, con el formato de entrada de `POST /api/v1/pqrs`.
- PostgreSQL 16 en Docker Compose y dos migraciones de Alembic: las 13 tablas del modelo de datos v1.1 y los datos semilla.
- Pruebas unitarias y de integración contra PostgreSQL.

Todavía no hay clasificación con IA, trabajador ni reintento manual (`POST /pqrs/{id}/clasificaciones`).

## Requisitos

- Python 3.12
- Docker con Docker Compose

## Primeros pasos (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copia `.env.example` como `.env` y completa `POSTGRES_PASSWORD` y `RADICA_DB_URL`. El archivo explica el formato. `.env` no se sube al repositorio.

```powershell
docker compose up -d db
alembic upgrade head
pytest
```

La base queda en `127.0.0.1:5433`. Usa esa dirección y no `localhost` en `RADICA_DB_URL`: en Windows, `localhost` prueba primero `::1` y cada conexión tarda minutos. Las pruebas de integración crean y borran su propia base temporal. Si `RADICA_DB_URL` no está definida, se omiten.

## Levantar la API

`.env` debe tener además `RADICA_LLAVE_CIFRADO` y `RADICA_LLAVE_HMAC`, distintas entre sí; `.env.example` explica cómo generarlas. Sin ellas la API no arranca.

```powershell
docker compose up -d db
alembic upgrade head
uvicorn --factory radica.main:crear_aplicacion
```

Swagger queda en http://127.0.0.1:8000/docs y la ruta técnica en http://127.0.0.1:8000/health. Rutas implementadas, bajo `/api/v1`:

| Ruta | Qué hace |
| --- | --- |
| `POST /pqrs` | Registra una PQRS; responde 201 con `Location` |
| `GET /pqrs` | Bandeja con semáforo, paginada y con filtros `semaforo`, `estado`, `tipo` e `idArea` |
| `GET /pqrs/{id}` | Detalle con la clasificación vigente y el texto enmascarado |
| `GET /pqrs/{id}/historial` | Eventos de auditoría en orden cronológico |
| `GET /configuracion/terminos` | Términos legales vigentes |

Los errores salen en Problem Details (`application/problem+json`); la validación responde 400.

## Estructura

```
src/radica/
  dominio/          valores, entidades y reglas puras (plazos, semáforo)
  aplicacion/       puertos y casos de uso
  adaptadores/      entrada (api, trabajador) y salida (postgres, ia, enmascarador, palabras_clave, cifrado)
  config.py         variables de entorno
  main.py           raíz de composición
migraciones/        Alembic
tests/              unitarios e integración
docs/               especificación, modelo de datos, diseño, contrato de la API y registro de uso de IA
api/bruno/          colección de la API (vacía)
```

## Documentación

- [docs/contexto.md](docs/contexto.md): alcance y reglas de la Entrega 3.
- [docs/modelo-datos.md](docs/modelo-datos.md): diccionario de datos y semillas.
- [docs/diseno/entrega-2-arquitectura.md](docs/diseno/entrega-2-arquitectura.md): arquitectura y decisiones (ADR).
- [docs/api/radica-api-v0.1.yaml](docs/api/radica-api-v0.1.yaml): contrato OpenAPI.
- [docs/uso-de-ia.md](docs/uso-de-ia.md): registro del uso de IA por sesión.
