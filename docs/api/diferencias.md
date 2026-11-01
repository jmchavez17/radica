# Diferencias entre la API implementada y el contrato

Compara [`openapi-implementada.json`](openapi-implementada.json), el OpenAPI que genera FastAPI en la Entrega 3, con [`radica-api-v0.1.yaml`](radica-api-v0.1.yaml), el contrato de diseño de la Entrega 2. Las razones vienen de [`docs/contexto.md`](../contexto.md) y de las decisiones registradas en [`docs/uso-de-ia.md`](../uso-de-ia.md). Revisado el 1-nov-2026 contra la API en Docker Compose.

## 1. Resumen

- Se implementan **6 de las 13 operaciones** del contrato, más la ruta técnica `GET /health`.
- Las URL finales son las mismas. El contrato pone `/api/v1` en `servers`; la API lo pone en cada ruta (`/api/v1/pqrs`). `/health` queda fuera de `/api/v1`.
- No hay autenticación: el OpenAPI no declara `security` y ninguna ruta responde 401 ni 403.
- Los errores de validación responden **400**, no el 422 que FastAPI usa por defecto.

## 2. Operaciones implementadas

| operationId | Método y ruta | Códigos del contrato | Códigos implementados | Diferencias |
| --- | --- | --- | --- | --- |
| `registrarPqrs` | `POST /api/v1/pqrs` | 201, 400, 401, 403 | 201, 400 | Sin 401 ni 403. 400 también si la fecha de radicación es posterior al registro. 500 en Problem Details si no hay término vigente (contexto.md 4.6) |
| `listarPqrs` | `GET /api/v1/pqrs` | 200, 401 | 200, 400 | 400 si un filtro o la paginación no son válidos (contexto.md 4.10). La respuesta tiene nombre: `PaginaPqrs` |
| `consultarPqrs` | `GET /api/v1/pqrs/{id}` | 200, 401, 404 | 200, 400, 404 | 400 si el id no es un entero mayor o igual a 1 |
| `solicitarClasificacionIa` | `POST /api/v1/pqrs/{id}/clasificaciones` | 202, 404, 409 | 202, 400, 404, 409 | El 202 tiene esquema propio: `ClasificacionSolicitada`. 409 si ya está PENDIENTE o si está RESPONDIDA o CERRADA |
| `consultarHistorial` | `GET /api/v1/pqrs/{id}/historial` | 200, 404 | 200, 400, 404 | El contrato no define el cuerpo; la API responde `{eventos: [...]}` |
| `listarTerminos` | `GET /api/v1/configuracion/terminos` | 200 | 200 | El contrato no define el cuerpo; la API responde `{terminos: [...]}` |
| — | `GET /health` | No está | 200, 503 | Ruta técnica para Docker: comprueba la conexión a la base (contexto.md 4.10) |

En todas las rutas, una ruta inexistente responde 404, un método no permitido 405 y un error no controlado 500, siempre en Problem Details y sin detalles internos.

## 3. Operaciones no implementadas

Están fuera de esta entrega por `docs/contexto.md` §2.3.

| operationId | Método y ruta | Historia | Backlog |
| --- | --- | --- | --- |
| `corregirClasificacion` | `PATCH /pqrs/{id}/clasificacion` | HU-06 | PB-08 (#8) |
| `registrarProrroga` | `POST /pqrs/{id}/prorroga` | HU-07 | PB-11 (#14) |
| `generarBorrador` | `POST /pqrs/{id}/borradores` | HU-10 | PB-14 (#17) |
| `aprobarBorrador` | `POST /borradores/{id}/aprobacion` | HU-11 | PB-15 (#15) |
| `importarCsv` | `POST /importaciones` | HU-02 | PB-02 (#3) |
| `consultarTablero` | `GET /tablero` | HU-12 | PB-16 (#21) |
| `exportarReporteSemaforo` | `GET /reportes/semaforo` | Entrevista V1 | PB-28 (Entrega 2, sección 2.1; sin issue) |

Por eso tampoco están sus esquemas: `CorreccionClasificacion`, `ResultadoCorreccion`, `SolicitudBorrador`, `Borrador` y `Aprobacion`.

## 4. Qué cambió y por qué

### 4.1 Validación: 400 en vez de 422

FastAPI responde 422 ante un error de validación y lo publica en cada ruta del OpenAPI. La API lo cambia por 400, con el formato `SolicitudInvalida` del contrato: Problem Details con `errores: [{campo, mensaje}]`. Los mensajes están en español y no repiten el valor recibido. El 422 también se quitó del OpenAPI generado, junto con los esquemas `HTTPValidationError` y `ValidationError` (contexto.md 4.11; sesión 2).

El contrato usa 422 para reglas de negocio de la corrección y de la prórroga. Esas operaciones no se implementan, así que la API no responde 422 en ninguna ruta.

### 4.2 Sin JWT: usuario semilla

El contrato pide `Authorization: Bearer` con roles FUNCIONARIO, COORDINADOR y ADMIN. La autenticación queda fuera de esta entrega (§2.3, PB-19, #22).

- Las acciones de persona (REGISTRAR y REINTENTO_IA) se atribuyen al usuario semilla 1, «Funcionario Sintético» (contexto.md 4.12; `modelo-datos.md`). Su `hash_contrasena` es `!`: no sirve para iniciar sesión.
- Por eso no hay 401 ni 403.
- La diferencia se cierra en el M5.

### 4.3 Formas de respuesta

El contrato describe estas respuestas sin esquema o con un objeto en línea. La API les da un esquema con nombre, con los campos que el contrato describe:

| Respuesta | Contrato | Implementación | Dónde se decidió |
| --- | --- | --- | --- |
| Historial | Solo la descripción | `Historial {eventos: [EventoHistorial]}` | Plan de la sesión 2 |
| Términos | Solo la descripción | `TablaTerminos {terminos: [TerminoLegal]}` | Plan de la sesión 2 |
| Reintento | Solo el ejemplo `{id, estadoIa}` | `ClasificacionSolicitada {id, estadoIa}` | Sesión 4, al agregar el reintento |
| Bandeja | Objeto en línea | `PaginaPqrs {pagina, total, elementos}` | Sesión 2 |

Los nombres de los esquemas del contrato se conservan: `PqrsNueva`, `PqrsCreada`, `PqrsResumen`, `PqrsDetalle`, `ClasificacionResumen`, `Vencimiento`, `Referencia` y `Problema`. La sesión 2 renombró los modelos para lograrlo.

### 4.4 Campos de las respuestas

- **`datosClave` se guarda, pero no se expone.** Claude devuelve `datosClave` y el trabajador lo guarda en `clasificacion.datos_extraidos` (JSONB). Ni el contrato ni la API lo muestran: `ClasificacionResumen` no tiene ese campo. Exponerlo es PB-09 (#13). Las salidas estructuradas no admiten un diccionario libre, así que viaja como lista de pares nombre y valor y el adaptador lo convierte (sesión 4).
- **El historial trae modelo y versión.** `EventoHistorial` agrega `idUsuario`, `modelo` y `versionInstrucciones`. La tabla `auditoria` no tiene esas dos columnas: se toman de la llamada OK de `llamada_ia` de la misma transacción, sin migración (sesión 4, D3).
- **`TerminoLegal` agrega `regla` e `idCalendario`.** `regla` es el texto que también sale en `vencimiento.regla`.
- **`responsable` siempre es `null` y `estado` nunca llega a ASIGNADA.** La asignación es PB-13 (#9). El ejemplo del contrato muestra el responsable 7 y el estado ASIGNADA.
- **`posiblesDuplicados` siempre es `[]`.** La detección es PB-27 (contexto.md 4.8).
- **`idArea` de la bandeja y `area` de `PqrsResumen` son el área sugerida** de la clasificación vigente, porque `pqrs.id_area` sigue nulo hasta PB-13 (contexto.md 4.9).
- **Campos que pueden salir nulos.** En el OpenAPI generado, los campos de las respuestas son obligatorios y pueden ser `null` (`atributo`, `area`, `resumen`, `modelo`, `versionInstrucciones`, `sede`, `responsable`, `clasificacion`). El contrato no marca obligatorios ni nulos en las respuestas.

### 4.5 Entrada de `POST /pqrs`

- **Correo.** El contrato usa `format: email`; la API usa una expresión regular (`usuario@dominio.tld`). `email-validator` rechaza por defecto los dominios `.test` de los datos sintéticos, así que no se agregó (sesión 2).
- **Fecha de radicación.** Debe traer zona horaria (`AwareDatetime`) y no puede ser posterior al registro: si lo es, 400 (propuesta aprobada en la sesión 2; supuesto que valida el coordinador).
- **Textos.** Se recortan los espacios. Un opcional vacío cuenta como ausente. `numeroDocumento` y `nombre` exigen al menos un carácter.

### 4.6 Restricciones que el OpenAPI generado no publica

- **`confianza`:** el contrato publica `minimum: 0, maximum: 1`; el generado, solo `number`. La regla se valida en `ResultadoClasificacion` y en el adaptador de Claude.
- **`resumen`:** el contrato publica `maxLength: 300`, el tamaño de la columna. La IA lo limita a 200 caracteres (contexto.md 4.9).
- **`id`:** el contrato lo publica como `int64`; el generado, como `integer` con `minimum: 1`.
- **`Problema.type`:** el contrato lo publica como `format: uri`; el generado, como `string`. Los valores son URI (`https://radica.local/problemas/...`).

### 4.7 Lo que la API hace y su OpenAPI no publica

- `POST /pqrs` envía la cabecera `Location: /api/v1/pqrs/{id}`. El contrato la documenta; el OpenAPI generado no.
- `GET /health` responde 503 en Problem Details si la base no responde. El OpenAPI generado solo publica el 200, con la descripción por defecto de FastAPI.
- El 500 de un término no configurado no figura en ninguna ruta.

### 4.8 Decisiones que no cambian el contrato

- **Sin `temperature`.** La solicitud a Claude no lleva `temperature` (contexto.md 4.9 pedía 0): Claude Haiku 5.5 y la versión de la API que usa el SDK 2.x la rechazan. La forma de la respuesta la fija un esquema de salidas estructuradas (sesión 4, D5).
- **El proveedor no se expone.** El proveedor de IA nunca sale en la API, como pide el contrato. Solo salen el modelo y la versión de instrucciones, que el contrato incluye en `ClasificacionResumen`.

## 5. Cómo se mantiene al día

`tests/unitarios/test_openapi_exportado.py` compara el archivo con el OpenAPI que genera `crear_app`, sin base de datos. Si cambia una ruta o un esquema, la prueba falla hasta regenerar el archivo con la API en marcha:

```powershell
curl.exe -s http://127.0.0.1:8000/openapi.json -o openapi.json
.venv\Scripts\python -m json.tool --indent 2 --no-ensure-ascii openapi.json docs\api\openapi-implementada.json
```
