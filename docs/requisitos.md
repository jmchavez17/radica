# Requisitos – Radica

## Descripción

Radica es un asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para la oficina de atención al usuario de una IPS de Cali, que debe responder dentro de términos legales. Registra cada PQRS, calcula su vencimiento con reglas, la clasifica con IA sobre el texto con los datos personales enmascarados y muestra una bandeja con semáforo. Todo el proyecto usa datos sintéticos.

Las historias y los requisitos no funcionales salen de las secciones 4 y 5 de la Entrega 1 (23 de octubre de 2026) y conservan sus identificadores, porque el README, `docs/contexto.md`, `docs/diseno/` y la matriz de trazabilidad del M4 los citan. El estado de cada historia se revisó contra el código y las pruebas de `main` el 14 de noviembre de 2026: «Hecha» solo si está implementada y tiene una prueba o evidencia verificable. Ese día pasaron las 390 pruebas unitarias de Python y las 42 de `web/`; las de integración (`tests/integracion/`) no se ejecutaron porque la base de datos no estaba levantada.

## Historias de usuario

### HU-01: Registrar una PQRS (PB-01)

Como funcionario de atención, quiero registrar una PQRS con su texto, canal y fecha y hora de radicación, para que el sistema calcule su plazo desde el momento correcto.

- Dado el formulario de registro, cuando guardo una PQRS sin texto o sin fecha de radicación, entonces el sistema no la guarda e indica el campo faltante.
- Dado un registro válido, cuando lo guardo, entonces el sistema asigna un número de radicado único y la fecha de radicación ya no puede editarse sin dejar registro.

Estado: Hecha

Evidencia: `tests/unitarios/test_api_errores.py::test_error_400_del_contrato` (sin texto: 400 con el campo en `errores[]`), `tests/unitarios/test_registrar_pqrs.py::test_registra_con_radicado_estado_y_vencimiento`, `web/src/pruebas/Registro.test.tsx` («muestra cada error 400 debajo de su campo…») y `tests/integracion/test_api_registro.py::test_datos_invalidos_responden_400_sin_guardar` (casos `sin-texto` y `sin-fecha`). La API no tiene ruta para editar la fecha y `auditoria` rechaza UPDATE y DELETE (`migraciones/versions/0001_esquema_inicial.py`).

### HU-03: Enmascarar datos personales (PB-04, PB-05)

Como responsable de protección de datos, quiero que los datos personales se reemplacen por marcadores antes de cualquier llamada a un servicio externo de IA, para cumplir la Ley 1581 de 2012.

- Dado un texto con una cédula, un teléfono y un correo, cuando se envía a clasificar, entonces el texto enviado contiene marcadores como `[CEDULA_1]`, `[TELEFONO_1]` y `[CORREO_1]` y ninguno de los valores originales.
- Dado un error en el enmascaramiento, cuando se intenta clasificar, entonces no se hace ninguna llamada externa y la PQRS queda para clasificación manual.

Estado: Hecha. Los nombres de terceros y las direcciones (PB-05, #18) siguen sin enmascararse.

Evidencia: `tests/unitarios/test_enmascarador.py::test_hu03_cedula_telefono_y_correo_quedan_con_marcadores` y `tests/unitarios/test_clasificar_pqrs.py::test_enmascaramiento_no_verificado_omite_la_ia_sin_ninguna_llamada` (estado OMITIDA y REQUIERE_REVISION, 0 llamadas).

### HU-04: Ver la clasificación sugerida (PB-06, PB-09)

Como funcionario de atención, quiero ver el tipo, el área sugerida, su nivel de confianza y un resumen de una línea, para decidir rápido sin leer todo el texto.

- Dada una PQRS registrada, cuando termina la clasificación, entonces se muestran tipo, área, confianza y resumen, marcados como sugerencia de la IA.
- Dada una sugerencia con confianza menor al umbral configurado, cuando se muestra, entonces la PQRS aparece como «requiere revisión» y no se asigna automáticamente.
- PROPUESTA: Dado que el proveedor de IA falla, cuando termina la clasificación, entonces sigue vigente la clasificación por reglas y la PQRS aparece como «requiere revisión».

Estado: Pendiente. `GET /api/v1/pqrs/{id}` ya devuelve tipo, área, confianza, resumen y `origen` IA. Falta mostrarlos en la interfaz, que no tiene vista de detalle, y exponer los datos clave (PB-09, #13), que se guardan pero la API no devuelve.

Evidencia: `tests/integracion/test_trabajador.py` (el detalle trae `origen` IA, confianza y resumen), `tests/unitarios/test_clasificar_pqrs.py::test_confianza_0_6_queda_vigente_pero_requiere_revision` y `::test_proveedor_caido_deja_fallida_y_requiere_revision`.

### HU-05: Detectar el nivel de riesgo en salud (PB-07)

Como funcionario de atención de una IPS, quiero que el sistema me alerte si un reclamo puede ser de riesgo vital o priorizado, para resolverlo dentro de su término en horas.

- Dado un reclamo que la IA sugiere como de riesgo vital, cuando termina la clasificación, entonces el sistema muestra una alerta inmediata y aplica el término de 24 horas mientras una persona lo confirma.
- Dado un nivel de riesgo fijado por una persona, cuando la IA sugiere un nivel menor, entonces el nivel no cambia: la IA puede subir el nivel, nunca bajarlo.
- Dado un reclamo de riesgo vital que corresponde a un menor de edad, cuando se confirma, entonces se aplica el término de 8 horas.

Estado: Pendiente. Ya se aplican los términos de 24 y 8 horas, y la IA no puede bajar el nivel vigente. Faltan la alerta inmediata (RNF-08) y la confirmación por una persona, que depende de corregir la clasificación (HU-06). Hoy el nivel que la IA no puede bajar es el de las reglas, porque una persona todavía no puede fijarlo.

Evidencia: `tests/unitarios/test_politica_riesgo.py` (`test_la_ia_baja_vital_a_simple_no_cambia_nada_y_pide_revision`, `test_vital_de_un_menor_acorta_a_8_horas`) y `tests/unitarios/test_plazos.py::test_casos_obligatorios_del_vencimiento` (casos 11 y 12). La tabla `notificacion` existe, pero nada en `src/` ni en `web/src/` la escribe ni muestra una alerta.

### HU-07: Ver el vencimiento calculado (PB-10, PB-11)

Como funcionario de atención, quiero ver la fecha y hora de vencimiento de cada PQRS, para saber cuál atender primero.

- Dada una petición general radicada el viernes 30 de octubre de 2026, cuando se calcula su vencimiento, entonces el sistema muestra el 24 de noviembre de 2026.
- Dado un reclamo de salud de riesgo simple radicado el 30 de octubre de 2026 a las 4:00 p. m., cuando se calcula su vencimiento, entonces el sistema muestra el 2 de noviembre de 2026 a las 4:00 p. m., porque las horas son corridas aunque ese día sea festivo.
- Dada una prórroga registrada antes del vencimiento, cuando se calcula el nuevo plazo, entonces no supera el doble del plazo inicial; registrada después del vencimiento, el sistema la rechaza.

Estado: Pendiente. El cálculo está hecho y la bandeja muestra el vencimiento. Falta la prórroga (PB-11, #14): solo existe la columna `pqrs.prorrogada`.

Evidencia: `tests/unitarios/test_plazos.py::test_casos_obligatorios_del_vencimiento` (los casos 1 y 9 son los dos primeros criterios) y la columna «Vence» de `web/src/Bandeja.tsx`.

### HU-08: Recibir alertas de vencimiento (PB-12)

Como funcionario de atención, quiero ver cada PQRS en verde, amarillo o rojo según el tiempo que le queda, para no dejar que ninguna se venza.

- Dada una PQRS a la que le queda menos tiempo que el umbral configurado, cuando abro la bandeja, entonces aparece en amarillo y en la lista de alertas.
- Dada una PQRS vencida sin respuesta aprobada, cuando abro la bandeja, entonces aparece en rojo en la parte superior.
- PROPUESTA: Dado un filtro de semáforo que no existe, cuando consulto la bandeja, entonces el sistema responde 400 e indica el filtro inválido.

Estado: Pendiente. El semáforo, el umbral configurable y el orden con las vencidas arriba están hechos. Falta la lista de alertas (#10).

Evidencia: `tests/unitarios/test_semaforo.py` (`test_amarillo_justo_en_el_umbral`, `test_el_umbral_es_configurable`), `tests/unitarios/test_consultas.py::test_la_bandeja_pone_las_vencidas_primero` y `tests/unitarios/test_api_errores.py::test_parametros_invalidos_son_400` (caso `semaforo=AZUL`).

### HU-10: Generar un borrador de respuesta (PB-14)

Como funcionario de atención, quiero un borrador de respuesta en lenguaje claro, para no empezar desde una hoja en blanco.

- Dada una PQRS con la información aportada por el área, cuando pido el borrador, entonces el texto usa solo esa información y la de la PQRS.
- Dado que falta un dato necesario, cuando se genera el borrador, entonces el sistema inserta `[COMPLETAR: dato]` en lugar de inventarlo.

Estado: Pendiente. Sin implementar (#17).

Evidencia: no hay código de borradores en `src/` ni en `web/src/`; solo existe la tabla `borrador` en `migraciones/versions/0001_esquema_inicial.py`.

### HU-11: Aprobar la respuesta (PB-15)

Como funcionario de atención, quiero aprobar o editar el borrador antes de que cuente como respuesta, para responder por su contenido.

- Dado un borrador sin aprobar, cuando intento marcar la PQRS como respondida, entonces el sistema no lo permite.
- Dado un borrador aprobado, cuando se guarda, entonces el historial registra quién lo aprobó, cuándo y si fue editado.

Estado: Pendiente. Sin implementar (#15); depende de HU-10.

Evidencia: no hay código de aprobación en `src/` ni en `web/src/`, ni una ruta que marque una PQRS como respondida.

### Otras historias de la Entrega 1

- HU-02 · Importar PQRS en lote (PB-02, PB-03): Pendiente. Sin implementar (#3 y #25).
- HU-06 · Corregir la clasificación (PB-08): Pendiente. No existe `PATCH /pqrs/{id}/clasificacion` (#8).
- HU-09 · Asignar a un área (PB-13): Pendiente. La API muestra el área sugerida, pero `pqrs.id_area` sigue vacío y no hay reasignación (#9).
- HU-12 · Supervisar vencimientos y temas (PB-16, PB-17): Pendiente. Sin tablero (#21 y #24).
- HU-13 · Consultar la trazabilidad (PB-18): Pendiente. `GET /api/v1/pqrs/{id}/historial` trae cada cambio con fecha, origen, valor anterior y nuevo, y modelo y versión si es de la IA. Faltan el usuario real, porque sin autenticación las acciones salen con el usuario semilla (#22), y la vista en la interfaz.

## No funcionales

| ID | Atributo | Requisito | Métrica | Verificación | Estado hoy |
| --- | --- | --- | --- | --- | --- |
| RNF-01 | Seguridad (confidencialidad) | Los datos personales se enmascaran antes de salir hacia el proveedor de IA | 0 cédulas, teléfonos, correos o números de historia clínica del conjunto de prueba en las solicitudes salientes | Prueba automática sobre el registro de solicitudes | Se cumple en pruebas: `test_demo_sintetico.py::test_ningun_dato_personal_sobrevive_al_enmascaramiento` (las 12 PQRS de la demo) y `test_clasificar_pqrs.py::test_la_solicitud_lleva_el_texto_enmascarado_el_catalogo_y_la_version` |
| RNF-09 | Adecuación funcional (corrección) | El vencimiento se calcula sin errores | 100 % de aciertos en al menos 30 casos límite: festivos, fines de semana, prórroga, horas corridas y cambio de año | Pruebas unitarias | Parcial: `test_plazos.py` tiene 31 pruebas, con los 13 casos obligatorios de `docs/contexto.md` §4.6, y pasan todas; ninguna es de prórroga, porque no está implementada |
| RNF-10 | Fiabilidad | Si el servicio de IA falla o tarda más de 30 s, la PQRS queda registrada con su plazo y pasa a clasificación manual | 0 PQRS perdidas con el servicio simulado caído | Prueba con el servicio desconectado | Se cumple en pruebas: el registro no espera a la IA (ADR-04) y `test_clasificar_pqrs.py::test_proveedor_caido_deja_fallida_y_requiere_revision` deja la PQRS con su plazo y en revisión. Cada intento tiene un límite de `IA_TIMEOUT_S` (15 s) |
| RNF-11 | Eficiencia de desempeño | La clasificación responde rápido | Percentil 95 menor a 15 s para PQRS de hasta 1.000 palabras | Medición en el entorno de demostración | Sin medir: cada llamada guarda `llamada_ia.latencia_ms`, pero el percentil 95 no se ha calculado |

## Cambios frente a la IA

| Qué propuso la IA | Qué hicimos | Por qué |
| --- | --- | --- |
| Agregar un quinto requisito no funcional, RNF-16 (PROPUESTA): todo cambio que llega a `main` pasa por la integración continua antes de desplegarse | Lo quitamos | El docente pide 4 no funcionales y la integración continua ya tiene su issue (#36) con criterio de hecho |
