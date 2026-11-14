# ADR-06 · Tecnologías: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 16 y React con TypeScript

Origen: `docs/diseno/entrega-2-arquitectura.md` §8 (Entrega 2, 31-oct-2026). Estado revisado contra el código de `main` el 14-nov-2026.

## Estado

**Aceptada** el 31-oct-2026. En la Entrega 2 era provisional hasta confirmarla con el equipo antes de empezar el Módulo 3. La parte de base de datos se detalla en [ADR-07](ADR-07-base-de-datos-postgresql.md).

- Evidencia de la aceptación: `docs/contexto.md` v1.0, del 31-oct-2026, fija el stack bajo «Stack (ADR-06)» (línea 51), y los commits de ese día configuran el proyecto en Python 3.12 (`78ae406`) y PostgreSQL 16 con Docker Compose (`a1a657a`).
- Evidencia en el código:
  - `pyproject.toml`: `requires-python = ">=3.12,<3.13"`, FastAPI 0.162.0, Pydantic 2.14.2, SQLAlchemy 2.1.6, Alembic 1.20.1 y el SDK `anthropic` 2.3.0.
  - `web/package.json`: React 19.3.1 y TypeScript 7.0.2.
  - `docker-compose.yml:28`: imagen `postgres:16.15-trixie`.
- Qué cambió y por qué:
  - mypy, que este ADR proponía para verificar los tipos, no se adoptó (sesión 1 de `docs/uso-de-ia.md`).
  - Se agregaron piezas que el ADR no nombraba, cada una aprobada en su sesión: uvicorn, psycopg, cryptography, python-dotenv, tzdata y Docker Compose; en la interfaz, Vite, Vitest y nginx (README, «Tecnologías»).
  - No se incluyó el SDK de Google, porque no hay adaptador de Gemini (ADR-05).

## Contexto

Había que elegir las tecnologías para programar desde el Módulo 3.

## Decisión

Python 3.12 con FastAPI para el backend, PostgreSQL 16 como base de datos y React con TypeScript para la interfaz.

## Alternativas

1. **Java con Spring Boot**, como en los ejemplos del curso.
2. **PHP con Laravel.**

## Consecuencias

Ventajas:

- Un solo lenguaje para la aplicación y la evaluación del Módulo 4, que puede reutilizar el clasificador por palabras clave y los adaptadores.
- Menos código propio de validación: Pydantic valida la entrada y la salida del modelo (`SalidaClaude`, `src/radica/adaptadores/salida/ia/claude.py:66-76`), y FastAPI genera el OpenAPI (`docs/api/openapi-implementada.json`).
- El SDK oficial de Anthropic es de Python.

Costos:

- El curso usa ejemplos en Java.
- Sin mypy, el tipado de Python no se verifica de forma automática.
- La experiencia del equipo en el lenguaje es desigual. La arquitectura no depende de él: los puertos se expresan igual con interfaces de Java.
