# ADR-03 · Enmascaramiento local obligatorio antes de cualquier llamada externa

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Aceptada** (31-oct-2026). Sigue vigente, sin cambios.

- Evidencia en el código:
  - El enmascaramiento es un paso del caso de uso y no del adaptador: `ClasificarPqrs.ejecutar` verifica el texto antes de llamar al clasificador y, si quedan datos del peticionario, deja la PQRS OMITIDA sin ninguna llamada (`src/radica/aplicacion/casos_de_uso/clasificar_pqrs.py:111-121`).
  - El enmascarador por reglas está en `src/radica/adaptadores/salida/enmascarador/reglas.py`, detrás del puerto `Enmascarador`.
  - El trabajador verifica con los datos del peticionario descifrados de la base (`tests/integracion/test_trabajador.py:180`).
  - El adaptador de Claude envía el texto delimitado como dato entre `<pqrs>` y `</pqrs>`, y quita esas etiquetas si vienen en el texto (`src/radica/adaptadores/salida/ia/claude.py:138-140`).
  - Pruebas: `tests/unitarios/test_clasificar_pqrs.py:287` (`test_enmascaramiento_no_verificado_omite_la_ia_sin_ninguna_llamada`) y `tests/unitarios/test_demo_sintetico.py:94` (ninguna cédula, teléfono, correo ni historia clínica de las 12 PQRS de la demo sobrevive al enmascaramiento).
- Pendiente: el enmascaramiento de nombres y direcciones con un modelo local (PB-05, #18). Por eso todo el proyecto usa datos sintéticos.

## Contexto

Las PQRS de una IPS contienen datos de salud, que la Ley 1581 de 2012 trata como sensibles, y el proveedor de IA es externo y está fuera del país.

## Decisión

Enmascarar localmente, verificar el resultado y enviar solo el texto enmascarado. Si la verificación falla, no se llama a la IA. El paso está en el caso de uso ClasificarPqrs, para que ningún adaptador nuevo pueda saltárselo.

## Alternativas

1. **Enviar el texto completo bajo un acuerdo de retención con el proveedor.** Se descartó: los datos sensibles saldrían del país igual (RNF-01 y RNF-02; riesgo R07).
2. **Usar solo un modelo local.** Se descartó para el MVP: sin transferencia de datos, pero con más costo de infraestructura y probablemente menos exactitud (ver ADR-05).

## Consecuencias

Ventajas:

- El proveedor nunca recibe identificadores, y el modelo no los necesita para clasificar.
- Una falla del enmascarador deja la PQRS en revisión, no filtra datos.

Costos:

- Las expresiones regulares no detectan todos los nombres y direcciones (de ahí PB-05), y el texto puede conservar información clínica no identificable.
- Riesgo de fuga residual. Se mitiga con la verificación posterior con las mismas reglas, datos sintéticos en todo el proyecto y el aval de jurídica antes de un piloto (V4).
