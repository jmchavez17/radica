# ADR-01 · Monolito modular con arquitectura hexagonal y núcleo Clean

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Aceptada** (31-oct-2026). Sigue vigente, con un cambio: hay 6 puertos de salida y no 8.

- Qué cambió y por qué: no se declararon `RedactorRespuesta`, `Notificador` ni `ArchivoTabular`, porque los borradores, el correo y la importación CSV están fuera del alcance de la Entrega 3 (`docs/contexto.md` §2.3; decisión de la sesión 1 en `docs/uso-de-ia.md`). Se agregó `Cifrador`, que no estaba en la Entrega 2 §5.3 (sesión 2).
- Evidencia en el código:
  - Las capas están en `src/radica/`: `dominio/`, `aplicacion/` (casos de uso y puertos), `adaptadores/entrada/` (api y trabajador), `adaptadores/salida/` (postgres, ia, enmascarador, palabras_clave y cifrado) y `main.py`, la raíz de composición.
  - Los puertos son `Protocol` en `src/radica/aplicacion/puertos/`: `PqrsRepository`, `AuditoriaRepository`, `ConfiguracionRepository`, `ClasificadorPqrs`, `Enmascarador` y `Cifrador`.
  - `tests/unitarios/test_arquitectura.py` comprueba la regla de dependencias: ninguna capa importa hacia afuera.
  - Un solo despliegue: la API y el trabajador son la misma imagen (`Dockerfile`) con dos comandos (`docker-compose.yml:45-80`).

## Contexto

El sistema combina reglas legales que deben ser exactas (plazos y riesgo), un proveedor de IA que puede cambiar o fallar y varias entradas (web, CSV y tareas programadas). Un diseño que mezcle HTTP, SQL e IA en las mismas clases impide probar los plazos sin red y cambiar de proveedor (RNF-09, RNF-13 y RNF-14 de la Entrega 1).

## Decisión

Arquitectura hexagonal (puertos y adaptadores) en un monolito modular, con el núcleo organizado como en Clean Architecture: dominio y casos de uso. Los puertos se declaran dentro del núcleo y los adaptadores dependen de ellos. `main.py` es el único lugar que conoce las clases concretas.

## Alternativas

1. **Capas tradicionales (controlador → servicio → DAO).** Sencillo y conocido, con menos archivos. Se descartó porque el servicio terminaría importando el SDK de IA y el DAO concreto: no se podrían probar los plazos sin infraestructura ni cambiar de proveedor sin tocar el servicio (Entrega 2 §5.4).
2. **Microservicios de registro, clasificación y notificación.** Se descartó: dos personas, seis semanas y unas 350 PQRS al mes no justifican varios despliegues ni comunicación por red entre servicios.
3. **Clean Architecture sola.** Ordena el núcleo, pero no dice cómo conectar las varias entradas y salidas; por eso se combinó con la hexagonal (Entrega 2 §5.4).

## Consecuencias

Ventajas:

- El dominio y los casos de uso se prueban sin base de datos ni red: las pruebas unitarias usan dobles de los puertos (`tests/unitarios/dobles.py`).
- Los adaptadores son intercambiables: con `IA_PROVIDER=ninguno` la raíz de composición no arma ningún clasificador de IA y el resto no cambia (`src/radica/main.py:62-74`).
- Un solo despliegue y una sola base de datos.

Costos:

- Más interfaces y archivos que un CRUD en capas, y una curva de aprendizaje para el equipo.
- Riesgo de sobreingeniería. Se mitiga creando puertos solo donde hay una variación real; por eso hoy son 6 y no 8.
