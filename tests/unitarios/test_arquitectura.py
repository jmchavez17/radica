"""Regla de dependencias de la arquitectura hexagonal (ADR-01).

dominio solo importa la biblioteca estándar y el propio dominio; aplicacion
importa además el dominio, nunca adaptadores ni librerías externas. La API
(adaptador de entrada) usa FastAPI y el núcleo, nunca SQLAlchemy, los
adaptadores de salida ni la configuración: eso lo conecta main.py.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PAQUETE = Path(__file__).resolve().parents[2] / "src" / "radica"

PERMITIDOS = {
    "dominio": ("radica.dominio",),
    "aplicacion": ("radica.dominio", "radica.aplicacion"),
    "adaptadores/entrada/api": (
        "radica.dominio",
        "radica.aplicacion",
        "radica.adaptadores.entrada.api",
        "fastapi",
        "pydantic",
        "starlette",
    ),
    "adaptadores/salida/palabras_clave": (
        "radica.dominio",
        "radica.aplicacion",
        "radica.adaptadores.salida.palabras_clave",
    ),
    "adaptadores/salida/ia": (
        "radica.dominio",
        "radica.aplicacion",
        "radica.adaptadores.salida.ia",
        "anthropic",
        "pydantic",
    ),
}


def _importados(archivo: Path) -> Iterator[str]:
    """Módulos que importa un archivo, con los imports relativos resueltos."""
    paquete = archivo.relative_to(PAQUETE.parent).with_suffix("").parts[:-1]
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete[: len(paquete) - nodo.level + 1]
                yield ".".join([*base, nodo.module] if nodo.module else base)
            else:
                yield nodo.module or ""


def _permitido(modulo: str, capas: tuple[str, ...]) -> bool:
    if modulo.split(".")[0] in sys.stdlib_module_names:
        return True
    return any(modulo == capa or modulo.startswith(capa + ".") for capa in capas)


def test_la_regla_detecta_imports_prohibidos() -> None:
    capas = PERMITIDOS["aplicacion"]
    assert _permitido("dataclasses", capas)
    assert _permitido("radica.dominio.valores", capas)
    assert not _permitido("sqlalchemy", capas)
    assert not _permitido("radica.adaptadores.salida.postgres", capas)
    assert not _permitido("radica.config", capas)
    api = PERMITIDOS["adaptadores/entrada/api"]
    assert _permitido("fastapi.responses", api)
    assert not _permitido("sqlalchemy", api)
    assert not _permitido("radica.adaptadores.salida.postgres.repositorios", api)


@pytest.mark.parametrize("capa", sorted(PERMITIDOS))
def test_la_capa_respeta_la_regla_de_dependencias(capa: str) -> None:
    archivos = sorted((PAQUETE / capa).rglob("*.py"))
    assert archivos, f"No se encontraron módulos en {capa}"
    prohibidos = [
        f"{archivo.relative_to(PAQUETE)} importa {modulo}"
        for archivo in archivos
        for modulo in _importados(archivo)
        if not _permitido(modulo, PERMITIDOS[capa])
    ]
    assert prohibidos == []
