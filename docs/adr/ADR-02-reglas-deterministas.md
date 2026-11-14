# ADR-02 · Plazos, semáforo y nivel de riesgo con reglas deterministas

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Aceptada** (31-oct-2026). Sigue vigente; la política de riesgo se precisó.

- Qué cambió y por qué: la Entrega 2 decía que la PoliticaDeRiesgo «toma el máximo entre las reglas y la IA». En el código la sugerencia de la IA se aplica solo si su vencimiento es igual o anterior al vigente y no baja la gravedad; si no, se guarda sin aplicar y la PQRS pide revisión. Comparar el vencimiento cubre también el cambio de tipo, que puede alargar el término aunque el nivel no baje (`docs/contexto.md` §4.9; decisión D7 de la sesión 4 en `docs/uso-de-ia.md`).
- Evidencia en el código:
  - Reglas puras, solo con biblioteca estándar: `CalculadoraDePlazos` (`src/radica/dominio/plazos.py:132`), `ReglaSemaforo` (`src/radica/dominio/semaforo.py:19`) y `PoliticaDeRiesgo` (`src/radica/dominio/riesgo.py:49`).
  - La política rechaza una sugerencia que alarga el plazo o baja la gravedad (`src/radica/dominio/riesgo.py:63-71`).
  - Los términos y los festivos son datos, no código: tablas `termino_legal` y `festivo` de `migraciones/versions/0001_esquema_inicial.py`, cargadas por `0002_datos_semilla.py` y leídas por el repositorio (`src/radica/adaptadores/salida/postgres/repositorios.py:446-448`).
  - El modelo no devuelve fechas: el esquema de su respuesta no tiene un campo de vencimiento (`src/radica/adaptadores/salida/ia/claude.py:66-76`).
  - Pruebas: `tests/unitarios/test_plazos.py`, `test_semaforo.py` y `test_politica_riesgo.py`.
- Pendiente: la prórroga (PB-11, #14). Sin ella, RNF-09 se cumple en parte (`docs/requisitos.md`).

## Contexto

Un plazo mal calculado puede terminar en tutela o sanción. Un modelo de lenguaje no garantiza exactitud aritmética ni trazabilidad del cálculo.

## Decisión

Las reglas viven en el dominio y la tabla de términos y los festivos son datos configurables. La IA solo sugiere tipo, atributo y riesgo; la CalculadoraDePlazos calcula el vencimiento y la PoliticaDeRiesgo decide si la sugerencia se aplica. Solo una persona puede bajar el riesgo o alargar un plazo.

## Alternativas

1. **Pedir la fecha de vencimiento al modelo.** Se descartó: no garantiza exactitud ni deja rastro de cómo se calculó.
2. **Reglas escritas directamente en el código, con los términos fijos.** Se descartó: un cambio normativo obligaría a cambiar código (RNF-13).

## Consecuencias

Ventajas:

- El cálculo es exacto, auditable y se prueba sin red.
- Un cambio normativo es un cambio de datos: un término nuevo con su vigencia.

Costos:

- La interpretación de la norma sigue siendo humana: regla de conteo, hora de cierre y vigencia de las circulares.
- Riesgo de interpretar mal los términos (R14). Se mitiga con la fuente normativa y la vigencia en cada término, la validación con jurídica (V4) y casos de prueba con festivos, fines de semana y cambio de año.
