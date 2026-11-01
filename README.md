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
- El OpenAPI que genera la API, en `docs/api/openapi-implementada.json`, comparado con el contrato en `docs/api/diferencias.md`.
- Pruebas unitarias y de integración contra PostgreSQL. Ninguna usa la red ni la clave real.

## Caso de uso implementado (CU-MVP)

«Registrar una PQRS y obtener su vencimiento y su clasificación» (`docs/contexto.md` §2.1). Cubre HU-01, HU-03, HU-04, HU-05 y HU-07, y en parte HU-08 y HU-13. Backlog: PB-01, PB-04, PB-06, PB-07, PB-10, PB-12 (parcial), PB-18 (parcial) y PB-21.

1. **Registro** (`POST /api/v1/pqrs`). En una sola transacción, y sin esperar a la IA:
   - valida la entrada;
   - cifra el nombre y el contacto del peticionario y guarda el documento como HMAC;
   - enmascara el texto con reglas;
   - hace la clasificación provisional por palabras clave;
   - elige el término legal vigente y calcula el vencimiento;
   - escribe los eventos de auditoría.

   Responde 201 con el radicado, el semáforo y `estadoIa` PENDIENTE.
2. **Clasificación con IA** (trabajador, en segundo plano):
   - toma la PQRS pendiente más antigua;
   - verifica que el texto enmascarado no tenga datos del peticionario: si los tiene, no llama a la IA;
   - la clasifica con Claude, o con las palabras clave si Claude falla;
   - aplica la política de riesgo: la IA puede subir el riesgo o acortar el plazo, nunca lo contrario;
   - guarda cada intento en `llamada_ia` y los cambios en `auditoria`.

   Con `IA_PROVIDER=ninguno` la PQRS queda OMITIDA y pide revisión.
3. **Consulta**: el detalle con la clasificación vigente y el texto enmascarado, la bandeja con semáforo, el historial y la tabla de términos. Si hace falta, el reintento manual de la IA.

## Tecnologías

Versiones fijadas en `pyproject.toml` y en las imágenes de `Dockerfile` y `docker-compose.yml`:

| Pieza | Versión | Uso |
| --- | --- | --- |
| Python | 3.12; imagen `python:3.12.16-slim-trixie` (3.12.10 en el entorno local) | Lenguaje |
| FastAPI | 0.162.0 | API REST y Swagger |
| uvicorn | 0.54.0 | Servidor de la API |
| Pydantic | 2.14.2 | Validación de entrada, salida y respuesta de la IA |
| SQLAlchemy | 2.1.6 | SQL parametrizado contra PostgreSQL |
| psycopg[binary] | 3.3.6 | Controlador de PostgreSQL |
| Alembic | 1.20.1 | Migraciones |
| PostgreSQL | 16; imagen `postgres:16.15-trixie` | Base de datos |
| anthropic | 2.3.0 | SDK oficial de Claude; modelo `claude-haiku-5-5` |
| cryptography | 50.0.2 | AES-256-GCM |
| python-dotenv | 1.2.4 | Lee `.env` fuera de Docker |
| tzdata | 2026.6 | Zona horaria America/Bogota en Windows |
| pytest | 9.2.0 | Pruebas (dependencia de desarrollo) |
| httpx | 0.28.1 | Dependencia de desarrollo |
| setuptools | 84.2.1 | Construcción del paquete |
| Docker Compose | Probado con v5.6.1 y Docker Engine 29.9.2 | Servicios `db`, `api` y `trabajador` |
| Bruno | Aplicación de escritorio | Colección de la API en `api/bruno/` |

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

## Migraciones y datos semilla

El esquema lo controlan las migraciones de Alembic de `migraciones/versions/`, escritas a mano. La aplicación nunca crea tablas desde los modelos.

| Migración | Qué hace |
| --- | --- |
| `0001_esquema_inicial` | Crea las 13 tablas del modelo de datos v1.1 (`docs/modelo-datos.md`): restricciones CHECK con nombre, llaves foráneas, 3 índices parciales y los disparadores que rechazan UPDATE, DELETE y TRUNCATE sobre `auditoria` |
| `0002_datos_semilla` | Carga el calendario de Colombia con 36 festivos (2026 y 2027), 9 términos legales, 7 áreas, 7 atributos de calidad y el usuario «Funcionario Sintético». Todo es sintético salvo los festivos y los términos legales |

```powershell
alembic upgrade head      # aplica las dos
alembic current           # muestra la versión aplicada
alembic downgrade base    # las deshace: borra las tablas y los datos
```

En Docker, la API ejecuta `alembic upgrade head` antes de servir.

## Levantar la API

`.env` debe tener además `RADICA_LLAVE_CIFRADO` y `RADICA_LLAVE_HMAC`, distintas entre sí; `.env.example` explica cómo generarlas. Sin ellas la API no arranca.

```powershell
docker compose up -d db
alembic upgrade head
uvicorn --factory radica.main:crear_aplicacion
```

Swagger queda en http://127.0.0.1:8000/docs y la ruta técnica en http://127.0.0.1:8000/health. Rutas implementadas, bajo `/api/v1` salvo `/health`:

| Ruta | Qué hace | Códigos |
| --- | --- | --- |
| `POST /pqrs` | Registra una PQRS; responde con `Location` | 201, 400, 500 |
| `GET /pqrs` | Bandeja con semáforo, paginada y con filtros `semaforo`, `estado`, `tipo` e `idArea` | 200, 400 |
| `GET /pqrs/{id}` | Detalle con la clasificación vigente y el texto enmascarado | 200, 400, 404 |
| `GET /pqrs/{id}/historial` | Eventos de auditoría en orden cronológico; los de la IA traen modelo y versión de instrucciones | 200, 400, 404 |
| `POST /pqrs/{id}/clasificaciones` | Reintento manual de la IA: responde `{id, estadoIa}` | 202, 400, 404, 409 |
| `GET /configuracion/terminos` | Términos legales vigentes | 200 |
| `GET /health` | Estado de la API y de la conexión a la base | 200, 503 |

Los errores salen en Problem Details (`application/problem+json`):

- **400**: datos o parámetros inválidos, con la lista `errores: [{campo, mensaje}]`. También una fecha de radicación posterior al registro.
- **404**: la PQRS no existe.
- **409**: el reintento no procede porque la PQRS ya está PENDIENTE o está RESPONDIDA o CERRADA.
- **500**: falta un término legal vigente para la clasificación, o hubo un error no controlado. Nunca lleva detalles internos.
- **503**: `/health` no llega a la base.
- En cualquier ruta, 404 si la ruta no existe y 405 si el método no está permitido.

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

Cada servicio tiene su verificación de salud:

- `db`, con `pg_isready`;
- `api`, con `/health`;
- `trabajador`, comprobando que su configuración es válida y que llega a la base. No comprueba que el bucle siga vivo: si el proceso muere, el contenedor termina y Compose lo reinicia.

La API espera a que la base esté sana, y el trabajador a la API. Verificación desde cero:

```powershell
docker compose down -v                # borra también la base de desarrollo
docker compose up -d --build --wait   # espera a que los tres servicios estén sanos
docker compose ps                     # db, api y trabajador: (healthy)
curl.exe -s http://127.0.0.1:8000/health
```

## Colección de Bruno

Levanta los servicios sin llamar a Claude. La colección se corre con `IA_PROVIDER=ninguno`:

```powershell
$env:IA_PROVIDER = "ninguno"; docker compose up -d --build
```

Abre la carpeta `api/bruno/` en Bruno, elige el entorno `local` y corre la colección completa y en orden. «Registrar una PQRS» guarda `idPqrs` y `radicadoPqrs` para las demás solicitudes; para correr una sola, antes hay que correr esa.

- «Reintentar sin esperar» espera 409 porque la PQRS sigue PENDIENTE. Si el trabajador, que revisa la cola cada 5 s, pasa justo entre el registro y esta solicitud, responde 202: en ese caso, corre de nuevo la colección.
- «Reintentar la clasificación con IA» espera 7 s antes de enviarse, para que el trabajador ya la haya dejado OMITIDA, y entonces espera 202.
- «Registrar un reclamo vital» tiene una fecha fija que ya venció: garantiza al menos una PQRS para «Bandeja en rojo».
- Cada corrida deja 2 PQRS sintéticas más en la base de desarrollo.

## Funcionalidades futuras (pendientes)

Fuera de esta entrega por `docs/contexto.md` §2.3. Las 13 tablas sí están creadas.

| Funcionalidad | Backlog | Estado |
| --- | --- | --- |
| Autenticación y roles con JWT | PB-19 (#22) | Pendiente |
| Corrección de la clasificación (`PATCH /pqrs/{id}/clasificacion`) | PB-08 (#8) | Pendiente |
| Prórroga y recálculo del vencimiento | PB-11 (#14) | Pendiente |
| Asignación automática de área o responsable | PB-13 (#9) | Pendiente |
| Notificaciones por correo y recordatorios programados | PB-26 | Pendiente |
| Importación de PQRS desde CSV | PB-02 (#3) | Pendiente |
| Borrador de respuesta y su aprobación | PB-14 (#17) y PB-15 (#15) | Pendiente |
| Tablero de vencimientos y volumen | PB-16 (#21) | Pendiente |
| Reporte semaforizado en CSV | PB-28 | Pendiente |
| Detección de posibles duplicados | PB-27 | Pendiente |
| Adaptador de Gemini como proveedor alterno | ADR-05 | Pendiente |
| Enmascaramiento de nombres y direcciones con un modelo local | PB-05 (#18) | Pendiente |
| Interfaz web | — | Pendiente |

PB-26, PB-27 y PB-28 salieron de la entrevista de la Entrega 2 y todavía no tienen issue.

## Decisiones y diferencias frente al diseño

El detalle de la API está en [docs/api/diferencias.md](docs/api/diferencias.md); las razones, en [docs/uso-de-ia.md](docs/uso-de-ia.md). Las principales:

- **Alcance de la API:** 6 de las 13 operaciones del contrato, más `GET /health`.
- **Validación:** responde 400 y no el 422 de FastAPI, también en el OpenAPI.
- **Sin autenticación:** las acciones de persona se atribuyen al usuario semilla «Funcionario Sintético».
- **Formas de respuesta:** el historial responde `{eventos}`, los términos `{terminos}` y el reintento `ClasificacionSolicitada`.
- **Datos clave:** `datosClave` de la IA se guarda en `clasificacion.datos_extraidos`, pero la API no lo expone (PB-09).
- **Historial:** trae el modelo y la versión de instrucciones, tomados de `llamada_ia`, sin columnas nuevas en `auditoria`.
- **Llamada a Claude:**
  - no lleva `temperature`;
  - el JSON lo fija un esquema de salidas estructuradas;
  - los precios para el costo son configurables.
- **Entrada del registro:**
  - el correo se valida con una expresión regular, porque `email-validator` rechaza los dominios `.test`;
  - una fecha de radicación futura responde 400.
- **Base de datos:** se publica en `127.0.0.1:5433`, porque el 5432 lo ocupa un PostgreSQL local.

## Uso de IA en el desarrollo

El proyecto se desarrolló con Claude Code (modelo Claude Opus 5.5). Se siguió el mismo método en cada sesión:

1. plan sin código;
2. aprobación del equipo;
3. cambios pequeños y probados;
4. un Pull Request que revisa el otro integrante.

[docs/uso-de-ia.md](docs/uso-de-ia.md) registra, por sesión, qué se pidió, qué propuso la IA, qué se aceptó, qué se corrigió o rechazó y cómo se verificó. Las reglas para el asistente están en [CLAUDE.md](CLAUDE.md).

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
- [docs/api/openapi-implementada.json](docs/api/openapi-implementada.json): OpenAPI que genera la API.
- [docs/api/diferencias.md](docs/api/diferencias.md): diferencias entre la API y el contrato.
- [docs/uso-de-ia.md](docs/uso-de-ia.md): registro del uso de IA por sesión.
