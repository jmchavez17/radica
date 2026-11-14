# ADR-05 · Proveedor de IA: Claude Haiku 5.5 como principal y Gemini 3.1 Flash-Lite como alterno

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Provisional, aplicada en parte.** La Entrega 2 la dejó provisional hasta la evaluación del Módulo 4, y esa evaluación (PB-22, #16) sigue abierta. En el código están Claude Haiku 5.5 como principal y el clasificador por palabras clave como respaldo; el adaptador de Gemini no existe.

- Qué cambió y por qué:
  - Gemini no se implementó: el adaptador quedó fuera del alcance de la Entrega 3 (`docs/contexto.md` §2.3). Por eso la sustitución por un segundo proveedor real no se ha probado.
  - Se agregó el modo `IA_PROVIDER=ninguno`: no se llama a ningún proveedor, la clasificación por reglas sigue vigente y la PQRS pide revisión (`docs/contexto.md` §4.9).
- Evidencia en el código:
  - `IA_PROVIDER` solo admite `claude` o `ninguno`, y el modelo por defecto es `claude-haiku-5-5` (`src/radica/config.py:23-26`).
  - La raíz de composición arma `ClasificadorConRespaldo([AdaptadorClaude, ClasificadorPalabrasClave])` con `claude` y ningún clasificador de IA con `ninguno` (`src/radica/main.py:62-74`).
  - `src/radica/adaptadores/salida/ia/` solo tiene `claude.py` y `respaldo.py`, y `pyproject.toml` no incluye un SDK de Google.
  - Cada intento queda en `llamada_ia` con sus tokens y su costo (`src/radica/adaptadores/salida/ia/claude.py:254-276`).

## Contexto

Se necesita un modelo con buena exactitud en español, una política de datos compatible con texto de salud enmascarado, latencia aceptable y bajo costo. Además, RNF-14 de la Entrega 1 pide ejecutar la evaluación con dos proveedores.

## Decisión

Claude Haiku 5.5 (API de Anthropic) como proveedor principal, Gemini 3.1 Flash-Lite como alterno detrás del mismo puerto `ClasificadorPqrs` y el clasificador por palabras clave como respaldo.

## Alternativas

1. **Claude Sonnet 5.5.** Más capaz, pero unas 19 veces más costoso por PQRS.
2. **Gemini 3.1 Flash-Lite como principal, en plan de pago.** Quedó como alterno.
3. **Un modelo local.** Sin transferencia de datos, pero con más costo de infraestructura y probablemente menos exactitud.

## Consecuencias

Ventajas:

- Costo marginal: menos de USD 1 al mes con el volumen de la IPS, según la comparación de la Entrega 1.
- Anthropic no usa por defecto las entradas ni las salidas de sus productos comerciales para entrenar modelos.
- El puerto deja lista la sustitución: un adaptador nuevo y la configuración (Entrega 2 §10).

Costos:

- La exactitud en español no se ha medido (PB-22, #16).
- El texto enmascarado sale del país (transferencia internacional, Ley 1581 de 2012, art. 26); falta validarlo con jurídica.
- Con un solo proveedor real, un cambio de precios o el retiro del modelo (R13) no tiene alterno listo. Mientras tanto, el respaldo por palabras clave y el modo `ninguno` mantienen el registro y los plazos sin IA.
