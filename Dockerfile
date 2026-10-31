# Imagen de la API y del trabajador: el mismo código con dos comandos (contexto.md 2.2).
# docker-compose.yml la construye una vez y la usan los servicios api y trabajador.
FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Solo lo que la aplicación necesita; .dockerignore deja fuera .env, .venv, pruebas y documentos.
COPY pyproject.toml ./
COPY src ./src
RUN pip install . && rm -rf build

COPY alembic.ini ./
COPY migraciones ./migraciones

RUN useradd --create-home --uid 10001 radica
USER radica

EXPOSE 8000
CMD ["uvicorn", "--factory", "radica.main:crear_aplicacion", "--host", "0.0.0.0", "--port", "8000"]
