# Radica

Asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para oficinas de atención al usuario que deben responder dentro de términos legales. Proyecto del Diplomado en Ingeniería de Software asistida por Inteligencia Artificial de la Universidad Santiago de Cali, por Jose Miguel Chávez Figueroa e Isabella Castaño Muñoz. Todo el proyecto usa datos sintéticos.

## Estado actual

Esta es la base común sobre la que se construye la Entrega 3. Hoy contiene:

- La estructura de la arquitectura hexagonal en `src/radica/`. Las carpetas de adaptadores están vacías.
- Los tipos de valor del dominio: tipo de PQRS, nivel de riesgo, canal, estado y estado de IA.
- El puerto `ClasificadorPqrs` y su contrato (`SolicitudClasificacion`, `ResultadoClasificacion`), sin implementaciones.
- PostgreSQL 16 en Docker Compose.
- Dos migraciones de Alembic: las 13 tablas del modelo de datos v1.1 y los datos semilla (calendario y festivos de Colombia 2026–2027, tabla de términos, áreas, atributos y un usuario sintéticos).
- Pruebas de las migraciones, de la regla de dependencias y del contrato de clasificación.

Todavía no hay API, casos de uso ni integración con IA.

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

## Estructura

```
src/radica/
  dominio/          tipos de valor; luego entidades y reglas puras
  aplicacion/       puertos; luego casos de uso
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
