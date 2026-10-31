# Radica

Asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para oficinas de atención al usuario que deben responder dentro de términos legales. Proyecto del Diplomado en Ingeniería de Software asistida por Inteligencia Artificial de la Universidad Santiago de Cali, por Jose Miguel Chávez Figueroa e Isabella Castaño Muñoz. Todo el proyecto usa datos sintéticos.

## Estado actual

Hoy contiene:

- El registro de PQRS por API: cifrado AES-256-GCM de los datos del peticionario con HMAC del documento, enmascaramiento por reglas, clasificación provisional, cálculo del vencimiento y auditoría, todo en una sola transacción.
- La consulta de una PQRS, la bandeja con semáforo, el historial de auditoría y la tabla de términos vigente.
- La clasificación con IA en segundo plano: el trabajador toma cada PQRS pendiente, verifica el enmascaramiento (si falla, no llama a la IA), la clasifica con Claude (`AdaptadorClaude`, con `ClasificadorPalabrasClave` de respaldo) y aplica la política de riesgo: la IA puede subir el riesgo o acortar el plazo, nunca lo contrario. Cada intento queda en `llamada_ia` con tokens y costo, sin el texto enviado ni la respuesta.
- El reintento manual de la IA: `POST /pqrs/{id}/clasificaciones`.
- Las reglas puras del dominio: selección del término, CalculadoraDePlazos, semáforo y PoliticaDeRiesgo.
- El puerto `ClasificadorPqrs` y su contrato. La clasificación provisional la hace `ClasificadorPalabrasClave`, con su diccionario versionado en `src/radica/adaptadores/salida/palabras_clave/diccionario.json`. Las instrucciones de Claude están en `src/radica/adaptadores/salida/ia/instrucciones/clasif-v1.0.md`.
- 12 PQRS sintéticas para la demostración en `datos/sinteticos/demo.json`, con el formato de entrada de `POST /api/v1/pqrs`.
- Docker Compose con `db`, `api` y `trabajador`, y dos migraciones de Alembic: las 13 tablas del modelo de datos v1.1 y los datos semilla.
- Una colección de Bruno en `api/bruno/`.
- Pruebas unitarias y de integración contra PostgreSQL. Ninguna usa la red ni la clave real.

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
| `GET /pqrs/{id}/historial` | Eventos de auditoría en orden cronológico; los de la IA traen modelo y versión de instrucciones |
| `POST /pqrs/{id}/clasificaciones` | Reintento manual de la IA: 202 `{id, estadoIa}`; 409 si ya está pendiente o la PQRS está respondida o cerrada |
| `GET /configuracion/terminos` | Términos legales vigentes |

Los errores salen en Problem Details (`application/problem+json`); la validación responde 400.

## Clasificación con IA (trabajador)

El registro nunca espera a la IA: deja la PQRS con `estadoIa` PENDIENTE. El trabajador es otro proceso del mismo código:

```powershell
radica-trabajador
```

Revisa la cola cada 5 s, toma la PQRS pendiente más antigua con `SELECT … FOR UPDATE SKIP LOCKED` y se detiene con Ctrl+C. Lo configuran estas variables de `.env`:

| Variable | Uso |
| --- | --- |
| `IA_PROVIDER` | `ninguno` (por defecto): no llama a ningún proveedor, la PQRS queda OMITIDA y pide revisión. `claude`: usa Claude y, si falla, las palabras clave |
| `IA_MODEL` | Modelo; por defecto `claude-haiku-5-5` |
| `IA_API_KEY` | Clave de Anthropic; obligatoria solo con `claude`. La pone una persona en `.env` |
| `IA_TIMEOUT_S` | Segundos por intento; por defecto 15 |
| `RADICA_UMBRAL_CONFIANZA` | Confianza mínima; por debajo, la PQRS pide revisión. Por defecto 0.75 |
| `IA_PRECIO_ENTRADA_USD_MTOK`, `IA_PRECIO_SALIDA_USD_MTOK` | Precios en USD por millón de tokens para `llamada_ia.costo_usd`; por defecto 0.10 y 0.50 (Claude Haiku 5.5). Verificarlos antes de reportar costos |

La solicitud a Claude no lleva `temperature`: Claude Haiku 5.5 y la versión de la API que usa el SDK 2.x la rechazan. La forma de la respuesta la fija un esquema de salidas estructuradas.

## Todo en Docker

```powershell
docker compose up -d --build
```

Levanta `db`, `api` (migra antes de servir, en http://127.0.0.1:8000) y `trabajador`. Una variable definida en la consola manda sobre la del `.env`; por ejemplo, para probar sin llamar a Claude: `$env:IA_PROVIDER = "ninguno"; docker compose up -d`. La imagen no lleva el `.env`.

## Colección de Bruno

Abre la carpeta `api/bruno/` en Bruno y elige el entorno `local`. «Registrar una PQRS» guarda el id en `idPqrs` para las demás solicitudes.

## Estructura

```
src/radica/
  dominio/          valores, entidades y reglas puras (plazos, semáforo, política de riesgo)
  aplicacion/       puertos y casos de uso
  adaptadores/      entrada (api, trabajador) y salida (postgres, ia, enmascarador, palabras_clave, cifrado)
  config.py         variables de entorno
  main.py           raíz de composición de la API y del trabajador
migraciones/        Alembic
tests/              unitarios e integración
docs/               especificación, modelo de datos, diseño, contrato de la API y registro de uso de IA
api/bruno/          colección de la API para Bruno
Dockerfile          imagen de la API y del trabajador
```

## Documentación

- [docs/contexto.md](docs/contexto.md): alcance y reglas de la Entrega 3.
- [docs/modelo-datos.md](docs/modelo-datos.md): diccionario de datos y semillas.
- [docs/diseno/entrega-2-arquitectura.md](docs/diseno/entrega-2-arquitectura.md): arquitectura y decisiones (ADR).
- [docs/api/radica-api-v0.1.yaml](docs/api/radica-api-v0.1.yaml): contrato OpenAPI.
- [docs/uso-de-ia.md](docs/uso-de-ia.md): registro del uso de IA por sesión.
