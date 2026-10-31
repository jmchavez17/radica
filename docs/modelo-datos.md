# Radica · Diccionario de datos del modelo v1.1 y datos semilla

Versión 1.1-a · 31 de octubre de 2026

Transcripción del diagrama aprobado `docs/diseno/03_modelo_datos.drawio` (Entrega 2, versión 1.1, sección 6) para generar la migración inicial. **La migración crea las 13 tablas tal como están aquí**, aunque esta entrega solo use algunas. No agregar tablas ni columnas.

**Único cambio frente al diagrama (aprobado el 31-oct-2026):** las columnas de tipo de PQRS pasan de VARCHAR(20) a **VARCHAR(25)**, porque `SOLICITUD_INFORMACION` tiene 21 caracteres. Aplica a `pqrs.tipo`, `clasificacion.tipo`, `termino_legal.tipo_pqrs` y `atributo_calidad.tipo_sugerido`. El diagrama se actualiza después.

**Convenciones generales** (Entrega 2, 6.3): PostgreSQL 16; llaves primarias con identidad generada; llaves foráneas con `ON DELETE RESTRICT`; fechas `TIMESTAMPTZ` (zona America/Bogota en la aplicación); valores cerrados con `CHECK`; `fecha_creacion` y `fecha` con valor por defecto `now()`.

---

## 1. Tablas

### calendario
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_calendario | INT | PK |
| nombre | VARCHAR(60) | UNIQUE, NOT NULL |
| activo | BOOLEAN | NOT NULL |

### festivo
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_calendario | INT | PK compuesta, FK → calendario |
| fecha | DATE | PK compuesta |
| descripcion | VARCHAR(100) | NOT NULL |

### termino_legal
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_termino | INT | PK |
| regimen | VARCHAR(10) | CHECK: GENERAL, SALUD |
| tipo_pqrs | **VARCHAR(25)** | CHECK: tipos de PQRS |
| nivel_riesgo | VARCHAR(12) | CHECK: niveles de riesgo |
| poblacion | VARCHAR(10) | CHECK: TODAS, MENOR |
| valor | SMALLINT | CHECK > 0 |
| unidad | VARCHAR(15) | CHECK: DIAS_HABILES, HORAS_CORRIDAS |
| id_calendario | INT NULL | FK → calendario. Obligatorio si unidad = DIAS_HABILES; nulo si HORAS_CORRIDAS (CHECK) |
| fuente_normativa | VARCHAR(150) | NOT NULL |
| vigente_desde | DATE | NOT NULL |
| vigente_hasta | DATE NULL | — |

### area
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_area | INT | PK |
| nombre | VARCHAR(100) | UNIQUE, NOT NULL |
| correo_notificacion | VARCHAR(120) | NOT NULL |
| activa | BOOLEAN | NOT NULL |

### atributo_calidad
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_atributo | INT | PK |
| nombre | VARCHAR(100) | UNIQUE, NOT NULL |
| definicion | TEXT | NOT NULL |
| tipo_sugerido | **VARCHAR(25)** | CHECK: tipos de PQRS |
| id_area_sugerida | INT NULL | FK → area |
| activo | BOOLEAN | NOT NULL |

### usuario
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_usuario | BIGINT | PK |
| nombre | VARCHAR(100) | NOT NULL |
| correo | VARCHAR(120) | UNIQUE, NOT NULL |
| hash_contrasena | VARCHAR(255) | NOT NULL |
| rol | VARCHAR(15) | CHECK: FUNCIONARIO, COORDINADOR, ADMIN |
| activo | BOOLEAN | NOT NULL |
| fecha_creacion | TIMESTAMPTZ | NOT NULL |

### peticionario
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_peticionario | BIGINT | PK |
| documento_hash | CHAR(64) | UNIQUE, NOT NULL (HMAC-SHA-256 en hexadecimal) |
| nombre_cifrado | BYTEA | NOT NULL (AES-256-GCM: nonce + texto cifrado) |
| contacto_cifrado | BYTEA | NOT NULL |
| fecha_creacion | TIMESTAMPTZ | NOT NULL |

### pqrs
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_pqrs | BIGINT | PK |
| radicado | VARCHAR(20) | UNIQUE, NOT NULL |
| id_peticionario | BIGINT | FK → peticionario, NOT NULL |
| canal | VARCHAR(20) | CHECK: DIME, CARTA, CORREO, WEB, VERBAL, BUZON, APLICATIVO_EPS |
| sede | VARCHAR(60) | NULL |
| fecha_radicacion | TIMESTAMPTZ | NOT NULL |
| texto_original_cifrado | BYTEA | NOT NULL |
| texto_enmascarado | TEXT | NOT NULL |
| tipo | **VARCHAR(25)** | CHECK: tipos de PQRS |
| id_atributo | INT NULL | FK → atributo_calidad |
| nivel_riesgo | VARCHAR(12) | CHECK: niveles de riesgo |
| paciente_menor | BOOLEAN | NOT NULL, por defecto false |
| id_termino | INT | FK → termino_legal, NOT NULL |
| fecha_vencimiento | TIMESTAMPTZ | NOT NULL |
| prorrogada | BOOLEAN | NOT NULL, por defecto false |
| estado | VARCHAR(20) | CHECK: REGISTRADA, REQUIERE_REVISION, CLASIFICADA, ASIGNADA, EN_RESPUESTA, RESPONDIDA, CERRADA |
| estado_ia | VARCHAR(12) | CHECK: PENDIENTE, COMPLETADA, FALLIDA, OMITIDA |
| id_area | INT NULL | FK → area |
| id_responsable | BIGINT NULL | FK → usuario |
| id_pqrs_relacionada | BIGINT NULL | FK → pqrs (posible duplicado) |
| fecha_respuesta | TIMESTAMPTZ NULL | — |
| fecha_creacion | TIMESTAMPTZ | NOT NULL |

### llamada_ia
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_llamada | BIGINT | PK |
| id_pqrs | BIGINT | FK → pqrs, NOT NULL |
| operacion | VARCHAR(12) | CHECK: CLASIFICAR, REDACTAR |
| proveedor | VARCHAR(30) | NOT NULL |
| modelo | VARCHAR(60) | NOT NULL |
| version_instrucciones | VARCHAR(20) | NOT NULL |
| intento | SMALLINT | NOT NULL |
| resultado | VARCHAR(25) | CHECK: OK, TIMEOUT, LIMITE_CUOTA, ERROR_PROVEEDOR, CREDENCIAL_INVALIDA, SALIDA_INVALIDA |
| tokens_entrada | INT | NOT NULL, por defecto 0 |
| tokens_salida | INT | NOT NULL, por defecto 0 |
| costo_usd | NUMERIC(10,6) | NOT NULL, por defecto 0 |
| latencia_ms | INT | NOT NULL |
| fecha | TIMESTAMPTZ | NOT NULL |

### clasificacion
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_clasificacion | BIGINT | PK |
| id_pqrs | BIGINT | FK → pqrs, NOT NULL |
| id_llamada_ia | BIGINT NULL | FK → llamada_ia |
| origen | VARCHAR(10) | CHECK: REGLAS, IA, PERSONA |
| tipo | **VARCHAR(25)** | CHECK: tipos de PQRS |
| id_atributo | INT NULL | FK → atributo_calidad |
| id_area | INT NULL | FK → area |
| nivel_riesgo | VARCHAR(12) | CHECK: niveles de riesgo |
| confianza | NUMERIC(4,3) | CHECK entre 0 y 1 |
| resumen | VARCHAR(300) | NULL |
| datos_extraidos | JSONB | NULL |
| vigente | BOOLEAN | NOT NULL. Índice único parcial: una sola vigente por id_pqrs |
| fecha | TIMESTAMPTZ | NOT NULL |

### borrador
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_borrador | BIGINT | PK |
| id_pqrs | BIGINT | FK → pqrs, NOT NULL |
| id_llamada_ia | BIGINT NULL | FK → llamada_ia |
| id_aprobador | BIGINT NULL | FK → usuario |
| origen | VARCHAR(10) | CHECK: IA, PLANTILLA |
| contenido | TEXT | NOT NULL |
| estado | VARCHAR(12) | CHECK: GENERADO, APROBADO, DESCARTADO. Índice único parcial: un solo APROBADO por id_pqrs |
| editado | BOOLEAN | NOT NULL, por defecto false |
| fecha_creacion | TIMESTAMPTZ | NOT NULL |
| fecha_aprobacion | TIMESTAMPTZ NULL | — |

### auditoria
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_evento | BIGINT | PK |
| id_pqrs | BIGINT | FK → pqrs, NOT NULL |
| id_usuario | BIGINT NULL | FK → usuario (nulo en eventos de IA o del sistema) |
| origen | VARCHAR(10) | CHECK: PERSONA, IA, SISTEMA |
| accion | VARCHAR(40) | NOT NULL |
| campo | VARCHAR(40) | NULL |
| valor_anterior | TEXT | NULL |
| valor_nuevo | TEXT | NULL |
| motivo | VARCHAR(300) | NULL |
| fecha | TIMESTAMPTZ | NOT NULL |

Solo inserción: disparador que rechaza UPDATE y DELETE.

### notificacion
| Columna | Tipo | Restricción |
| --- | --- | --- |
| id_notificacion | BIGINT | PK |
| id_pqrs | BIGINT | FK → pqrs, NOT NULL |
| tipo | VARCHAR(15) | CHECK: ASIGNACION, RECORDATORIO, VENCIDA, RIESGO_VITAL |
| destinatario | VARCHAR(120) | NOT NULL |
| estado | VARCHAR(10) | CHECK: PENDIENTE, ENVIADA, FALLIDA |
| intentos | SMALLINT | NOT NULL, por defecto 0 |
| fecha_programada | TIMESTAMPTZ | NOT NULL |
| fecha_envio | TIMESTAMPTZ NULL | — |

**Valores cerrados comunes.** Tipos de PQRS: PETICION, QUEJA, RECLAMO, SUGERENCIA, SOLICITUD_INFORMACION, CONSULTA. Niveles de riesgo: NO_APLICA, SIMPLE, PRIORIZADO, VITAL.

**Índices** (Entrega 2, 6.3): pqrs(fecha_vencimiento) para las abiertas; pqrs(estado_ia); pqrs(id_area); clasificacion(id_pqrs, vigente); auditoria(id_pqrs, fecha); el único de peticionario(documento_hash).

---

## 2. Datos semilla

Se cargan con una migración de datos, no a mano. Todo es sintético salvo los festivos y los términos legales.

### 2.1 Calendario
| id_calendario | nombre | activo |
| --- | --- | --- |
| 1 | Colombia nacional | true |

### 2.2 Festivos de Colombia 2026 y 2027 (calendario 1)

Fuente: Calendario de Colombia, «solo feriados» 2026 y 2027, consultado el 31-oct-2026; fechas contrastadas con la regla de traslado de la Ley 51 de 1983 (Pascua: 5 de abril de 2026 y 28 de marzo de 2027).

| Fecha | Descripción |
| --- | --- |
| 2026-01-01 | Año Nuevo |
| 2026-01-12 | Día de los Reyes Magos |
| 2026-03-23 | Día de San José |
| 2026-04-02 | Jueves Santo |
| 2026-04-03 | Viernes Santo |
| 2026-05-01 | Día del Trabajo |
| 2026-05-18 | Ascensión del Señor |
| 2026-06-08 | Corpus Christi |
| 2026-06-15 | Sagrado Corazón |
| 2026-06-29 | San Pedro y San Pablo |
| 2026-07-20 | Día de la Independencia |
| 2026-08-07 | Batalla de Boyacá |
| 2026-08-17 | Asunción de la Virgen |
| 2026-10-12 | Día de la Raza |
| 2026-11-02 | Todos los Santos |
| 2026-11-16 | Independencia de Cartagena |
| 2026-12-08 | Inmaculada Concepción |
| 2026-12-25 | Navidad |
| 2027-01-01 | Año Nuevo |
| 2027-01-11 | Día de los Reyes Magos |
| 2027-03-22 | Día de San José |
| 2027-03-25 | Jueves Santo |
| 2027-03-26 | Viernes Santo |
| 2027-05-01 | Día del Trabajo |
| 2027-05-10 | Ascensión del Señor |
| 2027-05-31 | Corpus Christi |
| 2027-06-07 | Sagrado Corazón |
| 2027-07-05 | San Pedro y San Pablo |
| 2027-07-20 | Día de la Independencia |
| 2027-08-07 | Batalla de Boyacá |
| 2027-08-16 | Asunción de la Virgen |
| 2027-10-18 | Día de la Raza |
| 2027-11-01 | Todos los Santos |
| 2027-11-15 | Independencia de Cartagena |
| 2027-12-08 | Inmaculada Concepción |
| 2027-12-25 | Navidad |

### 2.3 Tabla de términos (Entrega 2, 6.4)

| id | regimen | tipo_pqrs | nivel_riesgo | poblacion | valor | unidad | id_calendario | fuente_normativa | vigente_desde |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GENERAL | PETICION | NO_APLICA | TODAS | 15 | DIAS_HABILES | 1 | Ley 1755 de 2015, art. 14 | 2026-01-01 |
| 2 | GENERAL | SOLICITUD_INFORMACION | NO_APLICA | TODAS | 10 | DIAS_HABILES | 1 | Ley 1755 de 2015, art. 14 | 2026-01-01 |
| 3 | GENERAL | CONSULTA | NO_APLICA | TODAS | 30 | DIAS_HABILES | 1 | Ley 1755 de 2015, art. 14 | 2026-01-01 |
| 4 | GENERAL | QUEJA | NO_APLICA | TODAS | 15 | DIAS_HABILES | 1 | Ley 1755 de 2015, art. 14; entrevista V1 (confirmar con jurídica) | 2026-01-01 |
| 5 | GENERAL | SUGERENCIA | NO_APLICA | TODAS | 15 | DIAS_HABILES | 1 | Ley 1755 de 2015, art. 14 (confirmar con jurídica) | 2026-01-01 |
| 6 | SALUD | RECLAMO | SIMPLE | TODAS | 72 | HORAS_CORRIDAS | nulo | Supersalud, Circular Externa 2023151000000010-5 | 2026-01-01 |
| 7 | SALUD | RECLAMO | PRIORIZADO | TODAS | 48 | HORAS_CORRIDAS | nulo | Supersalud, Circular Externa 2023151000000010-5 | 2026-01-01 |
| 8 | SALUD | RECLAMO | VITAL | TODAS | 24 | HORAS_CORRIDAS | nulo | Supersalud, Circular Externa 2023151000000010-5 | 2026-01-01 |
| 9 | SALUD | RECLAMO | VITAL | MENOR | 8 | HORAS_CORRIDAS | nulo | Supersalud, Circular Externa 2026151000000007-5 | 2026-06-09 |

`vigente_desde` 2026-01-01 es un SUPUESTO de configuración (inicio de la tabla en el sistema), no la fecha de expedición de la norma. 2026-06-09 es la publicación de la Circular 2026151000000007-5 en el Diario Oficial 53.517.

Texto de la regla para la API: «Petición: 15 días hábiles», «Solicitud de información: 10 días hábiles», «Consulta: 30 días hábiles», «Queja: 15 días hábiles», «Sugerencia: 15 días hábiles», «Reclamo en salud, riesgo simple: 72 horas corridas», «Reclamo en salud, riesgo priorizado: 48 horas corridas», «Reclamo en salud, riesgo vital: 24 horas corridas», «Reclamo en salud, riesgo vital, paciente menor de edad: 8 horas».

### 2.4 Áreas (SINTÉTICAS)

Correos en el dominio reservado `.test`, que no existe en internet.

| id_area | nombre | correo_notificacion |
| --- | --- | --- |
| 1 | Atención al usuario | atencion@radica.test |
| 2 | Citas | citas@radica.test |
| 3 | Archivo clínico | archivo@radica.test |
| 4 | Autorizaciones | autorizaciones@radica.test |
| 5 | Facturación | facturacion@radica.test |
| 6 | Farmacia | farmacia@radica.test |
| 7 | Servicios asistenciales | asistencial@radica.test |

### 2.5 Atributos de calidad (SINTÉTICOS; el catálogo real lo entrega la IPS en V3)

| id | nombre | definicion | tipo_sugerido | id_area_sugerida |
| --- | --- | --- | --- | --- |
| 1 | Calidad humana | Trato del personal hacia el usuario: respeto, amabilidad y comunicación | QUEJA | 1 |
| 2 | Oportunidad | Demora en obtener una cita, un examen, una autorización o un servicio | RECLAMO | 4 |
| 3 | Accesibilidad | Barreras para acceder al servicio: horarios, canales, trámites o ubicación | RECLAMO | 1 |
| 4 | Seguridad del paciente | Hechos que pusieron o pueden poner en riesgo la salud del usuario | RECLAMO | 7 |
| 5 | Medicamentos | Entrega incompleta, tardía o equivocada de medicamentos | RECLAMO | 6 |
| 6 | Facturación y cobros | Cobros, copagos o cuotas que el usuario considera indebidos | RECLAMO | 5 |
| 7 | Información y documentos | Solicitudes de copias, certificados o información del servicio | SOLICITUD_INFORMACION | 3 |

El atributo «Calidad humana» con queja y 15 días hábiles viene de la entrevista V1; «Oportunidad» con id 2 coincide con los ejemplos de la API de la Entrega 2. Los demás son ejemplos del equipo.

### 2.6 Usuario

| id_usuario | nombre | correo | hash_contrasena | rol | activo |
| --- | --- | --- | --- | --- | --- |
| 1 | Funcionario Sintético | funcionario@radica.test | valor no utilizable (por ejemplo `!`), sin contraseña real | FUNCIONARIO | true |

Es el actor de las acciones de persona mientras no exista autenticación (M5).
