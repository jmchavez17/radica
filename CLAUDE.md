# Radica · guía para Claude Code

Radica es un asistente de gestión de PQRS (peticiones, quejas, reclamos y sugerencias) para la oficina de atención al usuario de una IPS de Cali. Registra cada PQRS, calcula su vencimiento con reglas, la clasifica con IA sobre el texto enmascarado y muestra una bandeja con semáforo. Es el proyecto del diplomado de la USC (Módulo 3; Entrega 3 el 4-nov-2026). Equipo: Jose Miguel Chávez Figueroa e Isabella Castaño Muñoz. Todo usa **datos sintéticos**.

## Fuentes de verdad

Leer antes de proponer código; `docs/contexto.md` manda sobre los demás:

- `docs/contexto.md`: alcance de la entrega, reglas del caso de uso, configuración y reglas no negociables.
- `docs/modelo-datos.md`: las 13 tablas y los datos semilla.
- `docs/diseno/entrega-2-arquitectura.md`: componentes, puertos, ADR-01 a ADR-06 e integración con IA.
- `docs/api/radica-api-v0.1.yaml`: contrato OpenAPI.

No se inventan tablas, columnas, rutas, reglas, roles, variables ni dependencias: si algo no está en esos documentos, se pregunta. `docs/contexto.md` §2.3 lista lo que **no** se implementa en esta entrega.

## Arquitectura (ADR-01)

Monolito modular hexagonal con núcleo Clean, en `src/radica/`:

- `dominio/`: valores, entidades y reglas puras. Solo biblioteca estándar.
- `aplicacion/`: casos de uso y puertos (`Protocol`). Solo importa `dominio`.
- `adaptadores/entrada/` (api, trabajador) y `adaptadores/salida/` (postgres, ia, enmascarador, palabras_clave, cifrado): implementan los puertos.
- `main.py`: raíz de composición, único lugar que conoce las clases concretas. Inyección por constructor.
- `config.py`: lectura de variables de entorno.

Regla de dependencias: siempre hacia adentro. Las rutas no tienen reglas de negocio ni SQL. La verifica `tests/unitarios/test_arquitectura.py`.

El puerto `ClasificadorPqrs` y su contrato están en `src/radica/aplicacion/puertos/clasificador.py`. Isabella implementa `ClasificadorPalabrasClave` sobre él: no cambiarlo sin acordarlo con ella.

## Comandos (PowerShell, desde la raíz)

```powershell
py -3.12 -m venv .venv            # Python 3.12; el python por defecto del equipo es otro
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up -d db           # PostgreSQL 16 en 127.0.0.1:5433 (el 5432 lo ocupa un PostgreSQL local)
alembic upgrade head              # migrar
pytest                            # probar; sin RADICA_DB_URL las pruebas de integración se omiten
radica-trabajador                 # trabajador de la IA; con IA_PROVIDER=ninguno no llama a nadie
docker compose up -d --build      # db, api y trabajador
```

Nunca llamar al `python` del sistema (se cuelga): usar siempre el del entorno virtual. Las pruebas no usan la red ni `IA_API_KEY`; el SDK de Anthropic se prueba con un cliente falso (`tests/unitarios/dobles.py`).

Sin activar el entorno: `.venv\Scripts\python -m pytest`, `.venv\Scripts\alembic upgrade head`.

`RADICA_DB_URL` usa `127.0.0.1`, no `localhost`: en Windows, `localhost` prueba primero `::1`, donde el contenedor no escucha, y cada conexión espera unos 130 s.

## Reglas no negociables (`docs/contexto.md` §6)

1. Ningún dato real, contraseña, token ni clave en el repositorio, en los commits, en los registros ni en los mensajes a herramientas de IA. `.env` está en `.gitignore`.
2. Los plazos los calculan reglas; nunca el modelo.
3. Ninguna llamada a la IA sin enmascaramiento verificado.
4. La IA nunca baja el riesgo ni alarga el plazo vigente.
5. El esquema lo controlan las migraciones de Alembic; nada de creación automática de tablas desde los modelos.
6. No declarar una prueba como exitosa si no se ejecutó.
7. Cambios pequeños, un commit por cambio comprobable, rama por funcionalidad y Pull Request revisado por el otro integrante.

Además:

- **Nunca leer ni mostrar `.env`** (ni `.env.*`, salvo `.env.example`) con ninguna herramienta o comando: nada de `cat`, `type`, `Get-Content`, `printenv`, ni `docker compose config` sin `--quiet`, que imprime los valores. Para saber si existe: `Test-Path .env`. Lo crea una persona a partir de `.env.example`.
- `main` es la base común: desde la sesión 2 todo entra por rama y Pull Request.
- Método: primero un plan sin código, esperar la aprobación y luego cambios pequeños que se prueban y se revisan. Commits en español y en imperativo, solo cuando el equipo los apruebe.
- Al cerrar cada sesión, agregar su tabla a `docs/uso-de-ia.md`.
