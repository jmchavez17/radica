# Radica

[![CI](https://github.com/jmchavez17/radica/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jmchavez17/radica/actions/workflows/ci.yml?query=branch%3Amain)

**Demostración en línea: https://radica-pqrs.up.railway.app** (la API, en [/docs](https://radica-pqrs.up.railway.app/docs)). Es pública y no pide usuario ni clave: úsala solo con datos sintéticos. Cómo usarla: [docs/manual-usuario.md](docs/manual-usuario.md). Cómo está desplegada: sección [Despliegue](#despliegue-railway).

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
- Una interfaz web mínima en `web/` (React con TypeScript): el formulario de registro y la bandeja con semáforo, filtros y paginación. No calcula nada: muestra lo que responde la API.
- Docker Compose con `db`, `api`, `trabajador` y `web`, y dos migraciones de Alembic: las 13 tablas del modelo de datos v1.1 y los datos semilla.
- Una colección de Bruno en `api/bruno/`.
- El OpenAPI que genera la API, en `docs/api/openapi-implementada.json`, comparado con el contrato en `docs/api/diferencias.md`.
- Pruebas unitarias y de integración contra PostgreSQL. Ninguna usa la red ni la clave real.
- El despliegue en Railway, con los mismos 4 servicios, en https://radica-pqrs.up.railway.app (ADR-08).

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

Versiones fijadas en `pyproject.toml`, `web/package.json` y en las imágenes de `Dockerfile`, `web/Dockerfile` y `docker-compose.yml`:

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
| httpx2 | 2.16.0 | Cliente del TestClient de Starlette y de las pruebas del SDK de Anthropic (dependencia de desarrollo) |
| setuptools | 84.2.1 | Construcción del paquete |
| Docker Compose | Probado con v5.6.1 y Docker Engine 29.9.2 | Servicios `db`, `api`, `trabajador` y `web` |
| Bruno | Aplicación de escritorio | Colección de la API en `api/bruno/` |
| React y react-dom | 19.3.1 | Interfaz web (ADR-06) |
| TypeScript | 7.0.2 | Revisión de tipos de la interfaz antes de construir (desarrollo) |
| Vite | 8.3.5 | Empaqueta la interfaz en archivos estáticos (desarrollo) |
| @types/react y @types/react-dom | 19.3.0 | Tipos de React para TypeScript (desarrollo) |
| Vitest | 5.0.5 | Pruebas de la interfaz (desarrollo) |
| jsdom | 30.1.3 | DOM simulado para las pruebas de la interfaz (desarrollo) |
| Node.js | Imagen `node:24.22.2-alpine3.24`, solo para construir; 26.13.0 en el equipo local, opcional | Construye y prueba la interfaz |
| nginx | Imagen `nginxinc/nginx-unprivileged:1.30.6-alpine3.24` | Sirve la interfaz sin privilegios y lleva `/api/`, `/health`, `/docs` y `/openapi.json` a la API |
| Railway | Plataforma; CLI 5.75.0 | Despliegue de los 4 servicios (ADR-08) |

## Requisitos

- Python 3.12
- Docker con Docker Compose
- Node.js, solo para correr las pruebas de la interfaz fuera de Docker (probado con 26.13.0)

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

## Pruebas

Ninguna prueba usa la red ni la clave de Anthropic: el SDK se prueba con un cliente falso (`tests/unitarios/dobles.py`) y la interfaz con un doble de `fetch`. Son dos grupos, y el CI corre los dos.

### API: pytest

Necesitas Python 3.12 y Docker. Desde la raíz del repositorio, en PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

En `.env` completa `POSTGRES_PASSWORD`, `RADICA_DB_URL`, `RADICA_LLAVE_CIFRADO` y `RADICA_LLAVE_HMAC`; `.env.example` dice cómo generar cada uno. Compose los pide aunque solo levantes la base. Luego:

```powershell
docker compose up -d --wait db
pytest
```

Resultado esperado: `472 passed`. Las 78 pruebas de integración crean su propia base temporal en ese servidor, le aplican las migraciones y la borran; no tocan la base de desarrollo. Si `RADICA_DB_URL` no está definida, se omiten. Para ver la cobertura, como en el CI: `pytest --cov=radica --cov-report=term-missing`.

### Interfaz: Vitest

Necesitas Node.js (el CI y la imagen usan 24.22.2; también pasa con 26.13.0):

```powershell
cd web
npm ci
npm test         # resultado esperado: 44 passed
npm run build    # tsc y vite build
```

Sin Node.js, las mismas pruebas corren en Docker: `docker build --target pruebas --progress=plain --build-context contrato=docs/api web`.

### Integración continua

El flujo [CI de GitHub Actions](https://github.com/jmchavez17/radica/actions/workflows/ci.yml) (`.github/workflows/ci.yml`) corre en cada push y en cada Pull Request a `main`:

- **Backend:** pytest con PostgreSQL 16 como servicio y con cobertura. Falla si alguna prueba se omite.
- **Interfaz:** `npm ci`, `npm test` y `npm run build` en `web/`.

Railway solo despliega un push cuando este flujo pasa (sección [Despliegue](#despliegue-railway)).

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

Los festivos llegan hasta 2027. Si el conteo en días hábiles de una PQRS pasa a 2028, el registro responde 500 de configuración en vez de contar como hábiles los festivos de ese año. Si el conteo que pasa a 2028 es el de la sugerencia de la IA, el trabajador deja la PQRS FALLIDA, con la clasificación por reglas vigente. Para 2028 hace falta una migración nueva con sus festivos, antes de noviembre de 2027.

## Levantar la API

`.env` debe tener además `RADICA_LLAVE_CIFRADO` y `RADICA_LLAVE_HMAC`, distintas entre sí; `.env.example` explica cómo generarlas. Sin ellas la API no arranca. `RADICA_UMBRAL_AMARILLO` es la fracción de tiempo restante desde la cual el semáforo pasa a amarillo; por defecto 0.5 (contexto.md 4.7).

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
- **500**: falta configuración para calcular el vencimiento, o hubo un error no controlado. Nunca lleva detalles internos. Falta configuración cuando no hay un término legal vigente para la clasificación, o cuando el conteo en días hábiles pasa por un año sin festivos cargados.
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

Levanta `db`, `api` (migra antes de servir, en http://127.0.0.1:8000), `trabajador` y `web` (la interfaz, en http://127.0.0.1:8080). Una variable definida en la consola manda sobre la del `.env`; por ejemplo, para probar sin llamar a Claude: `$env:IA_PROVIDER = "ninguno"; docker compose up -d`. La imagen no lleva el `.env`.

Cada servicio tiene su verificación de salud:

- `db`, con `pg_isready`;
- `api`, con `/health`;
- `trabajador`, comprobando que su configuración es válida y que llega a la base. No comprueba que el bucle siga vivo: si el proceso muere, el contenedor termina y Compose lo reinicia;
- `web`, pidiendo `/` a nginx con `wget`.

La API espera a que la base esté sana, y el trabajador y la interfaz esperan a la API. Verificación desde cero:

```powershell
docker compose down -v                # borra también la base de desarrollo
docker compose up -d --build --wait   # espera a que los cuatro servicios estén sanos
docker compose ps                     # db, api, trabajador y web: (healthy)
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8080/health   # la misma ruta, a través de la interfaz
```

## Despliegue (Railway)

La demostración corre en Railway: **https://radica-pqrs.up.railway.app**. Son los mismos 4 servicios de Compose; solo `web` tiene dominio público, y a la API se llega a través de nginx por la red privada, como en local. Por qué Railway y qué alternativas se miraron: [ADR-08](docs/adr/ADR-08-plataforma-de-despliegue.md).

Esta sección basta para desplegar Radica en otra cuenta de Railway con lo que hay en el repositorio. Los pasos 1, 2, 4, 6 y 7 son los comandos con los que se creó el proyecto `radica` el 18-nov-2026. El paso 5 (con `railway api`) y la carga de llaves del paso 3 se probaron el 19-nov-2026 en un proyecto aparte, que la cuenta de prueba no dejó pasar de un servicio. La tabla de servicios y la de variables se compararon ese día con la configuración real de `radica`.

### Lo que necesitas

- **Una cuenta de Railway conectada a GitHub.**
  - La prueba gratuita (USD 5 por 30 días) alcanza para un proyecto.
  - El plan Free no alcanza: admite 3 servicios por proyecto y duerme los que no reciben tráfico, como el trabajador.
  - La prueba tampoco deja crear un segundo proyecto con sus 4 servicios mientras el primero existe: para eso hace falta Hobby (USD 5 al mes).
- **Acceso de la app de GitHub de Railway al repositorio** (Railway → Account → GitHub → Configure repo access). Sin ese acceso, Railway puede construir un repositorio público, pero no despliega solo con cada push.
- **La CLI de Railway** (`npm install -g @railway/cli`; aquí se usó la 5.75.0), con la sesión iniciada: `railway login`.
- **Git Bash y Python 3.12** (`py -3.12`), para generar las llaves. No uses PowerShell 5.1 para cargarlas: el valor llega a la CLI con un BOM al principio.
- **Una clave de la API de Anthropic.** Ponle un límite de gasto en su consola. Sin clave se puede desplegar con `IA_PROVIDER=ninguno`: la PQRS se registra con su plazo y queda pidiendo revisión.

### Servicios

Los nombres tienen que ser exactamente `db`, `api`, `trabajador` y `web`, porque las variables los usan para encontrarse: `${{db.POSTGRES_PASSWORD}}`, `${{api.RADICA_DB_URL}}` y `api.railway.internal`.

| Servicio | Origen | Dockerfile | Comando de arranque | Healthcheck | Reinicio | Red |
| --- | --- | --- | --- | --- | --- | --- |
| `db` | Imagen `postgres:16.15-trixie` (la de Compose) | — | El de la imagen | — | Si falla | Volumen en `/var/lib/postgresql/data`; privada, `db.railway.internal:5432` |
| `api` | El repositorio, rama `main` | `Dockerfile` | `/bin/sh -c "alembic upgrade head && exec uvicorn --factory radica.main:crear_aplicacion --host 0.0.0.0 --port 8000"` (migra y sirve, como en Compose) | `/health`, 120 s | Si falla, hasta 10 veces | Privada, `api.railway.internal:8000` |
| `trabajador` | El repositorio, rama `main` | `Dockerfile` | `radica-trabajador` | — | Si falla, hasta 10 veces | Sin dominio; sale a la API de Anthropic |
| `web` | El repositorio, rama `main` | `web/Dockerfile.railway` | El de la imagen (nginx) | `/`, 60 s | Si falla, hasta 10 veces | Dominio público, al puerto 8080, con HTTPS de Railway |

### Variables

Los valores secretos no están aquí ni en el repositorio; se generan para cada despliegue (ver «Llaves»).

| Servicio | Variable | Valor |
| --- | --- | --- |
| `db` | `POSTGRES_DB`, `POSTGRES_USER` | `radica` |
| `db` | `POSTGRES_PASSWORD` | Secreta. Ver «Llaves» |
| `db` | `PGDATA` | `/var/lib/postgresql/data/pgdata`: el volumen trae `lost+found` en su raíz y PostgreSQL no inicia en una carpeta que no está vacía |
| `api` | `RADICA_DB_URL` | `postgresql+psycopg://${{db.POSTGRES_USER}}:${{db.POSTGRES_PASSWORD}}@${{db.RAILWAY_PRIVATE_DOMAIN}}:5432/${{db.POSTGRES_DB}}`, armada con referencias a `db` |
| `api` | `RADICA_LLAVE_CIFRADO`, `RADICA_LLAVE_HMAC` | Secretas. Ver «Llaves» |
| `api` | `IA_API_KEY` | Secreta: la clave de Anthropic |
| `api` | `IA_PROVIDER` | `claude` (o `ninguno`) |
| `api` | `IA_MODEL`, `IA_TIMEOUT_S`, `IA_PRECIO_ENTRADA_USD_MTOK`, `IA_PRECIO_SALIDA_USD_MTOK` | `claude-haiku-5-5`, `15`, `0.10` y `0.50`, como en `docker-compose.yml` |
| `api` | `RADICA_UMBRAL_AMARILLO`, `RADICA_UMBRAL_CONFIANZA` | `0.5` y `0.75` |
| `api` | `PORT` | `8000`: el puerto donde Railway hace el healthcheck |
| `trabajador` | Las 11 de `api` menos `PORT` | Referencias: `RADICA_DB_URL=${{api.RADICA_DB_URL}}`, y así cada una. El trabajador usa la misma base, las mismas llaves y la misma clave |
| `web` | `RADICA_RESOLVER` | `[fd12::10] ipv6=off`: el DNS interno de Railway, que nginx necesita para resolver `api.railway.internal` |
| `web` | `RADICA_API_URL` | `http://api.railway.internal:8000` |
| `web` | `PORT` | `8080` |
| `web` | `NGINX_ENTRYPOINT_WORKER_PROCESSES_AUTOTUNE` | `1`: un proceso de nginx por CPU del contenedor, no por CPU de la máquina. Es opcional |

### Llaves

| Variable | Qué es | Cómo se genera |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | Contraseña de la base. Va también dentro de `RADICA_DB_URL`, así que no puede tener `@ : / ? #` | `py -3.12 -c "import secrets,sys; sys.stdout.write(secrets.token_urlsafe(24))"` |
| `RADICA_LLAVE_CIFRADO` | Llave AES-256-GCM de los datos del peticionario: 32 bytes en base64 | `py -3.12 -c "import base64,os,sys; sys.stdout.write(base64.b64encode(os.urandom(32)).decode())"` |
| `RADICA_LLAVE_HMAC` | Llave del HMAC del documento: 32 bytes en base64, distinta de la anterior | El mismo comando, otra vez |
| `IA_API_KEY` | Clave de la API de Anthropic | En la consola de Anthropic |

Son nuevas para cada despliegue: no reutilices las del `.env`. No las cambies después de registrar PQRS, porque los datos cifrados con la llave anterior ya no se podrían leer. En el paso 3 se generan y se cargan en un solo comando, sin que el valor salga en pantalla. Para no imprimir valores, nunca uses `railway variable list` sin `--json` y un filtro.

### Paso a paso

En Git Bash, desde la raíz de un clon del repositorio. Reemplaza `<dueño>/radica` por tu repositorio o tu fork.

1. **Proyecto y servicios vacíos.** Si `railway add` pregunta por una variable, pulsa Enter.

   ```bash
   export MSYS_NO_PATHCONV=1      # que Git Bash no convierta rutas como /var/lib/... en rutas de Windows
   railway init --name radica
   for s in db api trabajador web; do railway add --service $s; done
   ```

2. **Variables de `db`, `api`, `trabajador` y `web`.** Van antes de conectar el código, para que el primer despliegue arranque bien:

   ```bash
   railway variable set POSTGRES_DB=radica POSTGRES_USER=radica PGDATA=/var/lib/postgresql/data/pgdata --service db --skip-deploys
   railway variable set 'RADICA_DB_URL=postgresql+psycopg://${{db.POSTGRES_USER}}:${{db.POSTGRES_PASSWORD}}@${{db.RAILWAY_PRIVATE_DOMAIN}}:5432/${{db.POSTGRES_DB}}' \
     IA_PROVIDER=claude IA_MODEL=claude-haiku-5-5 IA_TIMEOUT_S=15 IA_PRECIO_ENTRADA_USD_MTOK=0.10 IA_PRECIO_SALIDA_USD_MTOK=0.50 \
     RADICA_UMBRAL_AMARILLO=0.5 RADICA_UMBRAL_CONFIANZA=0.75 PORT=8000 --service api --skip-deploys
   for v in RADICA_DB_URL RADICA_LLAVE_CIFRADO RADICA_LLAVE_HMAC RADICA_UMBRAL_AMARILLO RADICA_UMBRAL_CONFIANZA \
            IA_PROVIDER IA_MODEL IA_API_KEY IA_TIMEOUT_S IA_PRECIO_ENTRADA_USD_MTOK IA_PRECIO_SALIDA_USD_MTOK; do
     railway variable set "$v=\${{api.$v}}" --service trabajador --skip-deploys
   done
   railway variable set 'RADICA_RESOLVER=[fd12::10] ipv6=off' RADICA_API_URL=http://api.railway.internal:8000 PORT=8080 \
     NGINX_ENTRYPOINT_WORKER_PROCESSES_AUTOTUNE=1 --service web --skip-deploys
   ```

3. **Llaves**, generadas y cargadas sin mostrarlas. `IA_API_KEY` se pega en el panel: servicio `api` → Variables → New Variable.

   ```bash
   py -3.12 -c "import secrets,sys; sys.stdout.write(secrets.token_urlsafe(24))" | railway variable set POSTGRES_PASSWORD --stdin --service db --skip-deploys
   for v in RADICA_LLAVE_CIFRADO RADICA_LLAVE_HMAC; do
     py -3.12 -c "import base64,os,sys; sys.stdout.write(base64.b64encode(os.urandom(32)).decode())" | railway variable set $v --stdin --service api --skip-deploys
   done
   ```

4. **La base.** El volumen se crea con el id del servicio: en la CLI 5.75.0, `--service db` con el nombre falla.

   ```bash
   DB=$(railway service list --json | py -3.12 -c "import json,sys; print(next(s['id'] for s in json.load(sys.stdin) if s['name']=='db'))")
   railway volume --service "$DB" add --mount-path /var/lib/postgresql/data
   railway service source connect --service db --image postgres:16.15-trixie
   ```

5. **Ajustes de `api`, `trabajador` y `web`.** Se toman de la tabla «Servicios». En el panel están en servicio → Settings: Dockerfile Path, Custom Start Command, Healthcheck Path y Restart Policy. Con la CLI:

   ```bash
   ENTORNO=$(railway status --json | py -3.12 -c "import json,sys; print(json.load(sys.stdin)['environments']['edges'][0]['node']['id'])")
   id_de() { railway service list --json | py -3.12 -c "import json,sys; print(next(s['id'] for s in json.load(sys.stdin) if s['name']=='$1'))"; }
   ajustar() {
     railway api 'mutation($s: String!, $e: String, $i: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(serviceId: $s, environmentId: $e, input: $i) }' \
       --raw-var s="$(id_de $1)" --raw-var e="$ENTORNO" --var i="$2"
   }
   ajustar api '{"dockerfilePath": "Dockerfile", "startCommand": "/bin/sh -c \"alembic upgrade head && exec uvicorn --factory radica.main:crear_aplicacion --host 0.0.0.0 --port 8000\"", "healthcheckPath": "/health", "healthcheckTimeout": 120, "restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 10}'
   ajustar trabajador '{"dockerfilePath": "Dockerfile", "startCommand": "radica-trabajador", "restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 10}'
   ajustar web '{"dockerfilePath": "web/Dockerfile.railway", "healthcheckPath": "/", "healthcheckTimeout": 60, "restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 10}'
   ```

6. **Conectar el código.** Cada conexión dispara el primer despliegue:

   ```bash
   for s in api trabajador web; do railway service source connect --service $s --repo <dueño>/radica --branch main; done
   ```

   Después, en el panel de cada uno (Settings → Source), activa «Wait for CI», para que solo se despliegue lo que pasó el CI. Hazlo al final: `source connect` vuelve a crear el disparador y lo deja desactivado.

7. **Dominio público:**

   ```bash
   railway domain --service web --port 8080
   ```

8. **Comprobar.**

   ```bash
   railway service list                          # los 4 servicios, Online
   curl -s https://<tu dominio>/health           # {"estado":"ok"}
   ```

   En la interfaz, registra una PQRS sintética. Con `IA_PROVIDER=claude`, en unos segundos `GET /api/v1/pqrs/{id}` muestra `estadoIa: COMPLETADA` y una clasificación con origen `IA`.

### Cómo se despliega un cambio

Al fusionar en `main` corre el CI y, si pasa, Railway construye y despliega `api`, `trabajador` y `web`; `db` no se toca. Si fusiona alguien que no es miembro del proyecto en Railway, como pasó con el PR #50, el despliegue queda en «Needs approval» hasta que un miembro lo apruebe en el panel. Mientras tanto sigue en línea el despliegue anterior.

### Qué cambió en el repositorio para desplegar

Nada de esto cambia lo que usa Compose:

- `web/nginx.conf` es una plantilla. La imagen oficial de nginx reemplaza `RADICA_RESOLVER` y `RADICA_API_URL` al arrancar; los valores por defecto, en `web/Dockerfile`, son los de Compose (`127.0.0.11 ipv6=off` y `http://api:8000`).
- `web/Dockerfile.railway` construye la interfaz desde la raíz del repositorio, porque Railway no pasa el contexto `contrato` de Compose. Su `.dockerignore` es `web/Dockerfile.railway.dockerignore`, y la prueba del contrato sigue corriendo dentro de la imagen.

### Costos

- **Railway:** el proyecto corre con la prueba (USD 5 por 30 días, sin tarjeta); en la primera hora consumió USD 0,0014. Cuando termine la prueba hay que pasar a Hobby (USD 5 al mes), porque el plan Free solo admite 3 servicios por proyecto y duerme el trabajador.
- **Anthropic:** la clave tiene un límite de gasto de USD 5 en su consola, y cada clasificación cuesta unos USD 0,0003 (#37).

## Interfaz web

Una interfaz mínima en `web/`, de la sesión 7: React 19 con TypeScript (ADR-06), empaquetada con Vite y servida por nginx. Se levanta con los demás servicios:

```powershell
$env:IA_PROVIDER = "ninguno"; docker compose up -d --build --wait
```

Abre http://127.0.0.1:8080. Tiene dos pestañas:

- **Registrar PQRS** (`#registro`): los campos y límites de `docs/contexto.md` §4.1; llama a `POST /api/v1/pqrs`.
  - Con 201 muestra el radicado, el estado, la clasificación provisional y el vencimiento con su semáforo, tal como los devuelve la API, y vacía el formulario.
  - Con 400 pone cada mensaje de `errores[]` debajo de su campo, según `campo` (`texto`, `peticionario.nombre`…); un campo que no está en el formulario va al resumen. Con otro error muestra el `title` y el `detail` de Problem Details.
  - La fecha se escribe en la hora local del campo y se envía como hora de Colombia (`-05:00`).
- **Bandeja** (`#bandeja`): `GET /api/v1/pqrs` con los filtros `semaforo`, `estado`, `tipo` e `idArea` (el id del área sugerida; la tabla lo muestra junto al nombre) y con `pagina` y `tamano`. Las filas salen en el orden en que las entrega la API: primero las vencidas y luego por vencimiento.

Cómo funciona:

- **Sin lógica de negocio.** El semáforo, las horas restantes, el vencimiento, el orden y la validación los calcula la API. El formulario lleva `noValidate`: los obligatorios y el formato los dice el 400. La interfaz solo da formato a fechas y números.
- **Mismo origen, sin CORS.** nginx sirve los archivos estáticos y lleva `/api/`, `/health`, `/docs` y `/openapi.json` a `http://api:8000` por la red de Compose. La interfaz usa rutas relativas, así que la API no necesita CORS y `src/` no cambia. Swagger queda también en http://127.0.0.1:8080/docs, con su propia `Content-Security-Policy`, porque carga Swagger UI de cdn.jsdelivr.net. La API sigue en http://127.0.0.1:8000 para Bruno.
- **Aviso.** Bajo el encabezado, en las dos pestañas: «Demostración con datos sintéticos: no ingrese datos personales reales».
- **Datos del peticionario.** Solo viven en el formulario hasta el registro. La interfaz no usa `localStorage`, `sessionStorage`, cookies ni la consola, y los campos del peticionario no se autocompletan. El navegador sí escribe por su cuenta en la consola cada respuesta 400 («Failed to load resource»), sin datos del peticionario.
- **Caché.** `/api/` sale con `no-store`, `index.html` con `no-cache` y `/assets/`, que lleva un hash en el nombre, con caché larga.
- **Contenedor.** Publicado solo en `127.0.0.1:8080`. nginx corre como el usuario 101, con el sistema de archivos de solo lectura (`/tmp` en memoria), sin capacidades, y con las cabeceras `Content-Security-Policy`, `X-Content-Type-Options` y `Referrer-Policy`.

`web/Dockerfile` construye en cuatro etapas: `dependencias` (`npm ci`, sin scripts de instalación), `pruebas` (Vitest), `construccion` (`tsc` y `vite build`) y la imagen de nginx. Si una prueba falla, la imagen no se construye. Para ver la salida de las pruebas:

```powershell
docker build --target pruebas --no-cache-filter pruebas --progress=plain --build-context contrato=docs/api web
```

Con Node.js instalado también corren fuera de Docker:

```powershell
cd web
npm ci
npm test         # Vitest con jsdom
npm run build    # tsc y vite build, en web/dist
```

Las pruebas están en `web/src/pruebas/` y no usan la red: un doble reemplaza `fetch`.

- `api.test.ts`: el cliente de la API, para 201, 400, 500, 502 y sin conexión, y la URL de la bandeja.
- `Registro.test.tsx` y `Bandeja.test.tsx`: los componentes, con el `act` de React.
- `App.test.tsx`: el aviso de datos sintéticos en el registro y en la bandeja.
- `contrato.test.ts`: compara las listas y los límites de `web/src/tipos.ts` con `docs/api/openapi-implementada.json`, que llega a la construcción por el contexto adicional `contrato`. Si la API cambia un enum, un límite o un filtro, falla.
- `sin-almacenamiento.test.ts`: revisa que el código no use el almacenamiento del navegador ni la consola. Además, la preparación de las pruebas falla si algo escribe en la consola.

Dependencias de npm, con versión exacta en `web/package.json` y `web/package-lock.json` (generado en la imagen de Node; `web/.npmrc` desactiva los scripts de instalación):

| Paquete | Para qué |
| --- | --- |
| `react`, `react-dom` | Componentes y montaje en el navegador (ADR-06). Son las únicas que llegan al navegador |
| `typescript` | Revisa los tipos antes de construir |
| `vite` | Empaqueta TS y TSX en archivos estáticos. Transforma el JSX por sí solo, sin `@vitejs/plugin-react`, que solo hace falta para la recarga en caliente del servidor de desarrollo |
| `@types/react`, `@types/react-dom` | Tipos de React |
| `vitest` | Corre las pruebas con la configuración de Vite |
| `jsdom` | DOM simulado para probar los componentes; sin Testing Library |

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
| Interfaz web: detalle, historial y reintento (el registro y la bandeja ya están en `web/`) | — | Pendiente |
| Alertas de vencimiento: la lista de amarillas y vencidas | PB-12 (#10), en parte | Pendiente |

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
- **Interfaz web:** es mínima (registro y bandeja) y llega a la API por un proxy de nginx en el mismo origen; la API no tiene CORS. El filtro de área es un número, porque la API no tiene catálogo de áreas.

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
web/                interfaz web: React con TypeScript, su Dockerfile y nginx.conf
  src/              componentes, cliente de la API, tipos y pruebas (src/pruebas/)
Dockerfile          imagen de la API y del trabajador
```

## Documentación

- [docs/manual-usuario.md](docs/manual-usuario.md): manual de usuario de la demostración en línea.
- [docs/requisitos.md](docs/requisitos.md): historias, criterios de aceptación y requisitos no funcionales.
- [docs/arquitectura.md](docs/arquitectura.md): diagramas C4 del código actual y despliegue; decisiones en [docs/adr/](docs/adr/) (ADR-01 a ADR-08).
- [docs/contexto.md](docs/contexto.md): alcance y reglas de la Entrega 3.
- [docs/modelo-datos.md](docs/modelo-datos.md): diccionario de datos y semillas.
- [docs/diseno/entrega-2-arquitectura.md](docs/diseno/entrega-2-arquitectura.md): arquitectura y decisiones (ADR).
- [docs/api/radica-api-v0.1.yaml](docs/api/radica-api-v0.1.yaml): contrato OpenAPI.
- [docs/api/openapi-implementada.json](docs/api/openapi-implementada.json): OpenAPI que genera la API.
- [docs/api/diferencias.md](docs/api/diferencias.md): diferencias entre la API y el contrato.
- [docs/uso-de-ia.md](docs/uso-de-ia.md): registro del uso de IA por sesión.
