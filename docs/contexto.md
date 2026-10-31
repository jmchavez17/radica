# Radica · Contexto para el desarrollo del MVP (Módulo 3)

Versión 1.0 · 31 de octubre de 2026 · Jose Miguel Chávez Figueroa e Isabella Castaño Muñoz

Este documento es la especificación del incremento que se entrega el **miércoles 4 de noviembre de 2026**, al cierre del módulo. El lunes 2 de noviembre a las 8:00 a. m. se muestran los avances al docente. Es la fuente de verdad para escribir código junto con:

| Documento | Qué aporta |
| --- | --- |
| `docs/diseno/entrega-2-arquitectura.md` | Arquitectura aprobada: componentes, puertos, ADR-01 a ADR-06, integración con IA |
| `docs/modelo-datos.md` | Diccionario de las 13 tablas del modelo v1.1 y datos semilla |
| `docs/api/radica-api-v0.1.yaml` | Contrato OpenAPI de diseño (13 operaciones; aquí se implementan 6) |
| `docs/diseno/*.drawio` y `*.png` | Diagramas de contexto, componentes, modelo de datos y flujo de IA |

**Regla general.** No se inventan tablas, columnas, rutas, reglas, roles ni dependencias. Si algo no está aquí ni en esos documentos, se pregunta antes de escribir código. Lo marcado como **SUPUESTO** es una decisión provisional del equipo, ya aprobada para esta entrega, que se validará con la IPS.

---

## 1. Qué es Radica

Asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para oficinas de atención al usuario que deben responder dentro de términos legales. El segmento inicial es una IPS de Cali. Radica registra cada PQRS, calcula su vencimiento con reglas, la clasifica con apoyo de un modelo de lenguaje sobre el texto con los datos personales enmascarados y muestra una bandeja con semáforo. Todo el proyecto usa **datos sintéticos**.

## 2. Alcance de esta entrega

### 2.1 Caso de uso CU-MVP: «Registrar una PQRS y obtener su vencimiento y su clasificación»

Cubre HU-01, HU-03, HU-04, HU-05 y HU-07, y en parte HU-08 y HU-13 (Entrega 1, sección 4). Backlog: PB-01, PB-04, PB-06, PB-07, PB-10, PB-12 (parcial), PB-18 (parcial) y PB-21.

### 2.2 Se implementa

| Pieza | Componente de la Entrega 2 |
| --- | --- |
| Registro de PQRS por API | Caso de uso RegistrarPqrs; `POST /api/v1/pqrs` |
| Cifrado de datos del peticionario y HMAC del documento | Sección 6.3 |
| Enmascaramiento por reglas con verificación | Puerto Enmascarador; EnmascaradorReglas (ADR-03) |
| Clasificación provisional por palabras clave y de alarma | ClasificadorPalabrasClave (PB-21) |
| Cálculo de vencimiento | CalculadoraDePlazos (ADR-02) |
| Semáforo | Regla Semaforo |
| Clasificación con IA en segundo plano | ClasificarPqrs, AdaptadorClaude, ClasificadorConRespaldo, trabajador (ADR-04, ADR-05) |
| Política de riesgo | PoliticaDeRiesgo (precisada en la sección 4.9) |
| Consulta, bandeja, historial y términos | `GET /pqrs/{id}`, `GET /pqrs`, `GET /pqrs/{id}/historial`, `GET /configuracion/terminos` |
| Reintento manual de la IA | `POST /pqrs/{id}/clasificaciones` (202) |
| Auditoría de solo inserción | Tabla auditoria y AuditoriaRepository |
| Contenedores | Docker Compose con db, api y trabajador |

### 2.3 No se implementa en esta entrega

No crear código para: autenticación y roles (JWT), corrección de clasificación (PATCH), prórroga, asignación automática de área, notificaciones por correo, tareas programadas de recordatorio, importación CSV, borradores y aprobación, tablero, reporte semaforizado, detección de duplicados, adaptador de Gemini, enmascaramiento de nombres con modelo local, interfaz web (salvo que se pida en una sesión aparte). Las 13 tablas sí se crean completas en la migración, porque son el modelo aprobado.

## 3. Tecnologías y estructura

**Stack (ADR-06):** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, pytest, SDK oficial `anthropic`, `cryptography`, Docker y Docker Compose, Bruno para la colección de la API. Zona horaria con `zoneinfo` (en Windows requiere `tzdata`). No agregar otras dependencias sin justificarlas y pedir aprobación.

**Arquitectura (ADR-01):** monolito modular hexagonal con núcleo Clean. Estructura propuesta; los nombres pueden ajustarse con justificación:

```
src/radica/
  dominio/          # entidades, valores y reglas puras: plazos, semáforo, política de riesgo. Sin imports de infraestructura
  aplicacion/       # casos de uso y puertos (Protocol): RegistrarPqrs, ClasificarPqrs, ConsultarPqrs, ListarBandeja, ConsultarHistorial
  adaptadores/
    entrada/api/        # FastAPI: rutas delgadas, esquemas de entrada y salida, manejo de errores
    entrada/trabajador/ # proceso que toma las PQRS con IA pendiente
    salida/postgres/    # SQLAlchemy: modelos y repositorios
    salida/ia/          # AdaptadorClaude e instrucciones versionadas
    salida/enmascarador/
    salida/palabras_clave/  # ClasificadorPalabrasClave y su diccionario (datos)
    salida/cifrado/
  config.py         # lectura de variables de entorno
  main.py           # raíz de composición: el único lugar que conoce las clases concretas
migraciones/        # Alembic
tests/
docs/
api/bruno/
```

**Regla de dependencias:** dominio no importa nada externo; aplicación importa dominio y declara los puertos; los adaptadores implementan los puertos. Las rutas no contienen reglas de negocio ni SQL. Inyección por constructor.

## 4. Reglas del caso de uso

### 4.1 Entrada de `POST /api/v1/pqrs`

Según el esquema `PqrsNueva` del contrato:

| Campo | Regla |
| --- | --- |
| canal | Obligatorio; uno de DIME, CARTA, CORREO, WEB, VERBAL, BUZON, APLICATIVO_EPS |
| sede | Opcional; máximo 60 caracteres |
| fechaRadicacion | Obligatoria; ISO 8601 **con zona horaria** |
| texto | Obligatorio; de 10 a 10.000 caracteres |
| pacienteMenorDeEdad | Opcional; por defecto false |
| peticionario.tipoDocumento | Obligatorio; uno de CC, TI, CE, PA, RC, PPT |
| peticionario.numeroDocumento | Obligatorio; máximo 20 caracteres |
| peticionario.nombre | Obligatorio; máximo 150 caracteres |
| peticionario.telefono | Opcional; máximo 20 caracteres |
| peticionario.correo | Opcional; formato de correo |

**PROPUESTA POR APROBAR EN LA SESIÓN:** rechazar con 400 una fecha de radicación posterior al momento del registro.

### 4.2 Peticionario

- `documento_hash` = HMAC-SHA-256, en hexadecimal (64 caracteres), de `tipoDocumento + ":" + numeroDocumento`, con la llave `RADICA_LLAVE_HMAC`.
- Si ya existe un peticionario con ese hash, se reutiliza sin sobrescribir sus datos.
- `nombre_cifrado` y `contacto_cifrado` (JSON con teléfono y correo) se cifran con AES-256-GCM, llave `RADICA_LLAVE_CIFRADO` (32 bytes en base64). Se guarda nonce + texto cifrado. `texto_original_cifrado` de pqrs se cifra igual.
- Ningún dato del peticionario sale en las respuestas de la API en esta entrega ni se envía a la IA.

### 4.3 Radicado

`RAD-<año de radicación>-<id_pqrs con 6 dígitos>`, por ejemplo RAD-2026-001287. Único.

### 4.4 Enmascaramiento (HU-03, RNF-01, RNF-02, ADR-03)

- Se hace al registrar y se guarda en `pqrs.texto_enmascarado`. La bandeja, la consulta y la IA solo usan ese texto.
- Detecta con reglas: cédulas y otros números de documento (6 a 10 dígitos, con o sin puntos), teléfonos colombianos (celulares de 10 dígitos que empiezan por 3, fijos con indicativo 60), correos y números de historia clínica (por ejemplo «HC 123456», «historia clínica n.º 123456»).
- Además reemplaza las apariciones exactas, sin distinguir mayúsculas ni tildes, del nombre, el documento, el teléfono y el correo que el peticionario dio en el formulario.
- Marcadores numerados por tipo: `[CEDULA_1]`, `[TELEFONO_1]`, `[CORREO_1]`, `[HC_1]`, `[NOMBRE_1]`. El mismo valor repetido recibe el mismo marcador.
- **Verificación:** `ClasificarPqrs` vuelve a pasar los detectores sobre el texto enmascarado y comprueba que no aparece ninguno de los valores del peticionario. Si algo queda, **no llama a la IA**: `estado_ia = OMITIDA`, `estado = REQUIERE_REVISION`, evento de auditoría. Falla cerrada.
- Límite conocido: no detecta nombres de terceros ni direcciones (PB-05, M4). Por eso solo datos sintéticos.

### 4.5 Clasificación provisional por reglas (PB-21)

Implementa el mismo puerto `ClasificadorPqrs` que la IA, para que sirva de clasificación provisional y de respaldo. Su diccionario es un archivo de datos versionado (YAML o JSON), no código. Responsable del diccionario y sus pruebas: Isabella.

Orden de evaluación, de lo más grave a lo menos grave (**SUPUESTO**, validar en V3):

1. Palabras de alarma de riesgo vital → tipo RECLAMO, nivel VITAL.
2. Palabras de riesgo priorizado → RECLAMO, PRIORIZADO.
3. Palabras de reclamo por un servicio de salud → RECLAMO, SIMPLE.
4. Palabras de queja, sugerencia, solicitud de información o consulta → ese tipo, NO_APLICA.
5. Si nada coincide → PETICION, NO_APLICA.

Área sugerida por palabras clave (por ejemplo «autorización» → Autorizaciones). Confianza fija de 0,5 para todo resultado por reglas. La clasificación por reglas siempre se guarda en `clasificacion` con `origen = REGLAS`.

Hasta que entre la rama de Isabella, la raíz de composición puede usar una versión mínima con unas pocas palabras; su rama la reemplaza.

### 4.6 Cálculo del vencimiento (HU-07, RNF-09, RNF-13, ADR-02)

**Selección del término** en `termino_legal` vigente a la fecha de radicación:

- Si el tipo es RECLAMO: por tipo, nivel de riesgo y población. Población MENOR solo cuando `pacienteMenorDeEdad = true` y el nivel es VITAL; si no, TODAS. Un RECLAMO nunca queda con NO_APLICA: el mínimo es SIMPLE.
- Si el tipo es otro: por tipo, sin importar el nivel de riesgo.
- Si no hay término vigente: error de configuración (500 con Problem Details y registro en el log), nunca un plazo inventado.

**Conteo** (**SUPUESTO**, validar en V3 y V4):

- `DIAS_HABILES`: se cuenta desde el día hábil siguiente a la fecha de radicación (sin importar la hora); son hábiles los lunes a viernes que no sean festivo del calendario del término. Vence a las 23:59:59 del último día, hora de Colombia.
- `HORAS_CORRIDAS`: fecha y hora de radicación + N horas, sin descontar festivos ni fines de semana.
- Todo en America/Bogota y guardado como TIMESTAMPTZ.

**Casos de prueba obligatorios** (recalculados con los festivos de `modelo-datos.md`):

| # | Tipo / nivel | Radicación | Término | Vencimiento esperado |
| --- | --- | --- | --- | --- |
| 1 | PETICION | vie 2026-10-30 16:00 | 15 días hábiles | 2026-11-24 23:59:59 |
| 2 | SOLICITUD_INFORMACION | vie 2026-10-30 | 10 días hábiles | 2026-11-17 23:59:59 |
| 3 | CONSULTA | vie 2026-10-30 | 30 días hábiles | 2026-12-16 23:59:59 |
| 4 | PETICION | sáb 2026-10-31 | 15 días hábiles | 2026-11-24 23:59:59 |
| 5 | PETICION | lun 2026-11-02 (festivo) | 15 días hábiles | 2026-11-24 23:59:59 |
| 6 | PETICION | vie 2026-12-18 | 15 días hábiles | 2027-01-13 23:59:59 (cambio de año) |
| 7 | QUEJA | jue 2026-12-24 | 15 días hábiles | 2027-01-19 23:59:59 |
| 8 | SOLICITUD_INFORMACION | mié 2026-04-01 (Semana Santa) | 10 días hábiles | 2026-04-17 23:59:59 |
| 9 | RECLAMO / SIMPLE | vie 2026-10-30 16:00 | 72 horas corridas | 2026-11-02 16:00 (festivo, no cuenta) |
| 10 | RECLAMO / PRIORIZADO | vie 2026-10-30 16:00 | 48 horas corridas | 2026-11-01 16:00 |
| 11 | RECLAMO / VITAL | vie 2026-10-30 16:00 | 24 horas corridas | 2026-10-31 16:00 |
| 12 | RECLAMO / VITAL, menor de edad | vie 2026-10-30 16:00 | 8 horas | 2026-10-31 00:00 |
| 13 | RECLAMO / VITAL, menor = false | vie 2026-10-30 16:00 | 24 horas | 2026-10-31 16:00 |

La `CalculadoraDePlazos` recibe el término y la lista de festivos como parámetros: se prueba sin base de datos.

### 4.7 Semáforo (HU-08)

**SUPUESTO** (validar en V3): fracción restante = (vencimiento − ahora) / (vencimiento − radicación).

- ROJO si ya venció (fracción ≤ 0).
- AMARILLO si la fracción es menor o igual a `RADICA_UMBRAL_AMARILLO` (0,5 por defecto).
- VERDE en otro caso.

Se calcula al consultar, no se guarda. `horasRestantes` con un decimal; negativo si venció. Coincide con los ejemplos 7.3 a 7.5 de la Entrega 2.

### 4.8 Respuesta del registro

201 con cabecera `Location: /api/v1/pqrs/{id}` y el cuerpo `PqrsCreada` del contrato: id, radicado, estado REGISTRADA, estadoIa PENDIENTE, clasificacionProvisional (origen REGLAS), vencimiento (fecha, regla en texto, semáforo) y `posiblesDuplicados: []` (la detección no está en esta entrega). La regla en texto sale del término, por ejemplo «Reclamo en salud, riesgo simple: 72 horas corridas».

El registro, la clasificación provisional, el cálculo y los eventos de auditoría ocurren en una sola transacción. El registro **nunca espera a la IA** (RNF-10).

### 4.9 Clasificación con IA (HU-04, HU-05, ADR-03 a ADR-05)

**Trabajador.** Proceso aparte (mismo código, otro punto de entrada y otro servicio en Docker Compose). Cada pocos segundos toma la PQRS más antigua con `estado_ia = PENDIENTE` usando `SELECT … FOR UPDATE SKIP LOCKED` y ejecuta `ClasificarPqrs`.

**ClasificarPqrs**, en este orden:

1. Verifica el enmascaramiento (4.4). Si falla: OMITIDA, sin llamada.
2. Arma la solicitud interna `SolicitudClasificacion` (Entrega 2, 10.1): texto enmascarado, catálogo vigente de tipos, atributos con definición y áreas leídos de la base de datos, versión de instrucciones `clasif-v1.0`.
3. Llama al puerto `ClasificadorPqrs`. Con `IA_PROVIDER=claude`, la raíz de composición entrega `ClasificadorConRespaldo([AdaptadorClaude, ClasificadorPalabrasClave])`.
4. Aplica la política de riesgo (abajo) y guarda.

Con `IA_PROVIDER=ninguno` no se llama a ningún proveedor: `estado_ia = OMITIDA`, la clasificación por reglas sigue vigente, `estado = REQUIERE_REVISION` y queda el evento IA_OMITIDA con el motivo «IA desactivada por configuración». Así opera Radica sin IA (Entrega 2, 10.4, nivel 2).

**AdaptadorClaude.**

- SDK oficial de Anthropic, modelo `IA_MODEL` (claude-haiku-5-5), temperatura 0, máximo 400 tokens de salida, timeout `IA_TIMEOUT_S` (15 s).
- Instrucciones en un archivo versionado dentro del adaptador. El texto de la PQRS va delimitado como dato (`<pqrs>…</pqrs>`), con la indicación de no seguir instrucciones que aparezcan dentro de él (LLM01). El modelo no tiene herramientas ni ejecuta acciones.
- Salida JSON validada con Pydantic: `tipo` del catálogo, `idAtributo` e `idArea` existentes o nulos, `nivelRiesgo` del catálogo, `confianza` entre 0 y 1, `senalesRiesgo` (lista), `resumen` de máximo 200 caracteres, `datosClave` (objeto de textos). Si no cumple: un reintento y luego `SalidaInvalida`; nunca se aplica a medias.
- Errores: tiempo agotado, 429 o 5xx → hasta 2 reintentos con esperas de 2 y 8 s; 400, 401 o 403 → sin reintento. Todo error del SDK se traduce a `ProveedorNoDisponible` o `SalidaInvalida`.
- Costo: `tokens_entrada × precio_entrada + tokens_salida × precio_salida`, con precios configurables (Entrega 1: USD 0,10 y 0,50 por millón de tokens para Haiku 5.5, consultados el 22-oct-2026; verificar antes de reportar).
- Cada intento queda en `llamada_ia` (operación CLASIFICAR, proveedor, modelo, versión de instrucciones, intento, resultado, tokens, costo, latencia). **No se guarda el texto enviado ni la respuesta completa.**
- El circuito abierto y la alerta de costo diario quedan para después; no implementarlos ahora.

**Política de riesgo** (RNF-07; precisión del ADR-02 aprobada para esta entrega):

- Orden de gravedad: NO_APLICA < SIMPLE < PRIORIZADO < VITAL.
- Se calcula el vencimiento que tendría la clasificación de la IA con la CalculadoraDePlazos.
- Si ese vencimiento es **igual o anterior** al vigente, la clasificación de la IA queda vigente (`origen = IA`, la anterior pasa a `vigente = false`) y se actualizan en pqrs tipo, id_atributo, nivel_riesgo, id_termino y fecha_vencimiento.
- Si sería **posterior** (la IA alargaría el plazo o bajaría el riesgo), se guarda la sugerencia con `vigente = false`, se conserva la clasificación vigente y la PQRS pasa a `REQUIERE_REVISION`. Solo una persona puede alargar un plazo (fuera de esta entrega).
- Si la confianza es menor a `RADICA_UMBRAL_CONFIANZA` (0,75), o si la IA marca PRIORIZADO o VITAL en un tipo distinto de RECLAMO, la PQRS pasa a `REQUIERE_REVISION` aunque la sugerencia quede vigente.
- En otro caso, `estado = CLASIFICADA`. `pqrs.id_area` sigue nulo: la asignación (PB-13) no está en esta entrega; la API muestra el área sugerida de la clasificación vigente.
- Resultado final: `estado_ia = COMPLETADA`. Si el respaldo por palabras clave tuvo que responder porque Claude falló: `estado_ia = FALLIDA`, la clasificación por reglas sigue vigente y `estado = REQUIERE_REVISION`.

Casos de prueba de la política (con un clasificador falso, sin red): la IA sube SIMPLE a PRIORIZADO → queda vigente y el plazo pasa de 72 a 48 horas; la IA baja VITAL a SIMPLE → no cambia nada y la PQRS pide revisión; la IA cambia PETICION por SOLICITUD_INFORMACION → queda vigente (10 días es antes que 15); confianza 0,6 → vigente pero REQUIERE_REVISION; proveedor caído → FALLIDA y REQUIERE_REVISION; enmascaramiento no verificado → OMITIDA y 0 llamadas.

### 4.10 Consultas y reintento

| Ruta | Regla |
| --- | --- |
| `GET /api/v1/pqrs/{id}` | `PqrsDetalle`: clasificación vigente (con modelo y versión de instrucciones si es de IA), vencimiento con semáforo, texto enmascarado. 404 si no existe |
| `GET /api/v1/pqrs` | `PqrsResumen` paginado (`pagina`, `tamano` hasta 100); filtros `semaforo`, `estado`, `tipo`, `idArea` (área sugerida vigente). Orden: vencidas primero, luego por vencimiento ascendente. 400 si un filtro no es válido |
| `GET /api/v1/pqrs/{id}/historial` | Eventos de auditoría en orden cronológico: fecha, origen, acción, campo, valor anterior, valor nuevo, motivo y, si es de IA, modelo y versión. 404 si no existe |
| `GET /api/v1/configuracion/terminos` | Términos vigentes: régimen, tipo, nivel, población, valor, unidad, calendario, fuente normativa, vigencia |
| `POST /api/v1/pqrs/{id}/clasificaciones` | Pone `estado_ia = PENDIENTE` y responde 202 `{id, estadoIa}`. 404 si no existe; 409 si ya está PENDIENTE o si el estado es RESPONDIDA o CERRADA |
| `GET /health` | Ruta técnica para Docker; comprueba la conexión a la base de datos. No está en el contrato |

### 4.11 Errores

- Formato Problem Details (RFC 9457), `application/problem+json`, con `type`, `title`, `status`, `detail`, `instance` y, en validación, `errores: [{campo, mensaje}]` (ver 7.3 de la Entrega 2).
- FastAPI responde 422 por defecto ante errores de validación: **se cambia a 400**, como dice el contrato.
- 404 para recursos inexistentes; 409 para estados que no permiten la operación; 500 sin detalles internos ni trazas.
- Nunca se exponen el proveedor de IA, las instrucciones, la clave ni datos del peticionario.

### 4.12 Auditoría (HU-13, RNF-06)

Eventos mínimos en `auditoria`:

| Acción | Origen | Cuándo |
| --- | --- | --- |
| REGISTRAR | PERSONA (usuario semilla) | Al crear la PQRS |
| CLASIFICAR_REGLAS | SISTEMA | Clasificación provisional |
| CALCULAR_VENCIMIENTO | SISTEMA | Al calcular o recalcular, con valor anterior y nuevo |
| CLASIFICAR_IA | IA | Sugerencia aplicada, un evento por campo que cambió |
| SUGERENCIA_IA_NO_APLICADA | SISTEMA | La IA alargaría el plazo |
| IA_FALLIDA, IA_OMITIDA | SISTEMA | Falla del proveedor o del enmascaramiento |
| REINTENTO_IA | PERSONA | `POST /clasificaciones` |

La tabla es de solo inserción: un disparador de PostgreSQL rechaza UPDATE y DELETE sobre auditoria (equivale al REVOKE de la sección 6.3 mientras la aplicación y las migraciones usan el mismo usuario).

**Usuario actor.** Sin autenticación en esta entrega, las acciones de persona se atribuyen al usuario semilla «Funcionario Sintético» (ver `modelo-datos.md`). Es una diferencia documentada frente al contrato (JWT), que se cierra en el M5.

## 5. Configuración

Variables de entorno; `.env.example` lleva los nombres y valores no sensibles, nunca secretos:

| Variable | Uso | Ejemplo en .env.example |
| --- | --- | --- |
| POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD | Contenedor de PostgreSQL | radica, radica, vacío |
| RADICA_DB_URL | Conexión de API y trabajador | vacío |
| RADICA_LLAVE_CIFRADO | AES-256-GCM, 32 bytes en base64 | vacío + instrucción para generarla |
| RADICA_LLAVE_HMAC | HMAC del documento | vacío + instrucción para generarla |
| IA_PROVIDER | `claude` o `ninguno` | ninguno |
| IA_MODEL | Modelo | claude-haiku-5-5 |
| IA_API_KEY | Clave de la API de Anthropic | vacío |
| IA_TIMEOUT_S | Tiempo máximo por intento | 15 |
| RADICA_UMBRAL_CONFIANZA | Confianza mínima | 0.75 |
| RADICA_UMBRAL_AMARILLO | Fracción restante para amarillo | 0.5 |

La aplicación no arranca si falta una variable obligatoria y lo dice sin mostrar valores.

## 6. Reglas no negociables

1. Ningún dato real, contraseña, token ni clave en el repositorio, en los commits, en los registros ni en los mensajes a herramientas de IA. `.env` está en `.gitignore`. No leer ni imprimir `.env`.
2. Los plazos los calculan reglas; nunca el modelo.
3. Ninguna llamada a la IA sin enmascaramiento verificado.
4. La IA nunca baja el riesgo ni alarga el plazo vigente.
5. El esquema lo controlan las migraciones de Alembic; nada de creación automática de tablas desde los modelos.
6. No declarar una prueba como exitosa si no se ejecutó.
7. Cambios pequeños, un commit por cambio comprobable, rama por funcionalidad y Pull Request revisado por el otro integrante.

## 7. Supuestos abiertos (validar con la IPS)

| Supuesto | Dónde vive | Validación |
| --- | --- | --- |
| Palabras clave y de alarma | Diccionario del clasificador | V3 |
| Regla de conteo y cierre a las 23:59:59 | CalculadoraDePlazos | V3 y V4 |
| Umbral del semáforo de 0,5 | Variable de entorno | V3 |
| Catálogo de áreas y atributos | Datos semilla | V3 |
| Vigencia desde 2026-01-01 de los términos generales | Datos semilla | Jurídica (V4) |
| Rechazar fechas de radicación futuras | Validación del registro | Coordinador |
