# ADR-04 · Clasificación en segundo plano, con cola en la base de datos y clasificación provisional por reglas

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Aceptada** (31-oct-2026). Sigue vigente, con dos cambios:

1. El trabajador no comparte servidor con la API: es otro servicio de Docker Compose, con la misma imagen y otro comando (`docker-compose.yml:63-80`). Así lo pidió `docs/contexto.md` §4.9 («proceso aparte»), y Compose lo vuelve a iniciar si se cae (`restart: unless-stopped`).
2. No hay una tarea programada que reintente tres veces. Los reintentos están dentro de cada llamada al proveedor: hasta 3 intentos, con esperas de 2 y 8 s (`src/radica/adaptadores/salida/ia/claude.py:48-49`). Si todos fallan, la PQRS queda FALLIDA y en REQUIERE_REVISION, y una persona puede volver a encolarla con `POST /api/v1/pqrs/{id}/clasificaciones` (`src/radica/adaptadores/entrada/api/rutas.py:148-165`). Las tareas programadas están fuera del alcance de la Entrega 3 (`docs/contexto.md` §2.3).

- Evidencia en el código:
  - El registro no espera a la IA: la API solo arma el clasificador provisional por palabras clave (`src/radica/main.py:87`) y deja `estadoIa` en PENDIENTE.
  - La cola es la columna `pqrs.estado_ia`; el trabajador toma la pendiente más antigua con `SELECT … FOR UPDATE SKIP LOCKED` (`src/radica/adaptadores/salida/postgres/repositorios.py:245-251`) y, si no hay, espera 5 s (`src/radica/adaptadores/entrada/trabajador/bucle.py:24`).
  - Un error inesperado deja la PQRS FALLIDA para no tomarla otra vez (`bucle.py:47-54`).
  - Pruebas: `tests/integracion/test_trabajador.py:134` (dos trabajadores no toman la misma PQRS), `test_trabajador.py:146` (error inesperado) y `tests/unitarios/test_clasificar_pqrs.py:262` (proveedor caído: FALLIDA y REQUIERE_REVISION).

## Contexto

Registrar no puede depender de la IA (RNF-10), y la respuesta del modelo puede tardar varios segundos.

## Decisión

La PQRS se registra con estado de IA PENDIENTE y un trabajador en segundo plano la procesa. Al registrar se hace una clasificación provisional por palabras clave y palabras de alarma, así que la PQRS tiene un plazo provisional desde el primer momento.

## Alternativas

1. **Llamada síncrona dentro de `POST /pqrs`.** Se descartó: el registro dependería de la IA y tardaría lo que tarde el modelo.
2. **Broker de mensajes (RabbitMQ, o Redis con Celery).** Se descartó: con unas 350 PQRS al mes no se justifica otra pieza de infraestructura.

## Consecuencias

Ventajas:

- Sin infraestructura adicional: la cola es una columna de la tabla `pqrs`.
- Los reintentos son idempotentes, porque cada PQRS tiene una sola clasificación vigente (índice único parcial, ver ADR-07).
- Las palabras de alarma marcan un posible riesgo vital aunque la IA no responda.

Costos:

- La bandeja debe refrescarse para mostrar la clasificación final.
- La cola depende de `SKIP LOCKED`, que ata la solución a un motor que lo tenga (ver ADR-07).
- Una PQRS FALLIDA no se reintenta sola: queda en revisión hasta que una persona la vuelve a encolar.
