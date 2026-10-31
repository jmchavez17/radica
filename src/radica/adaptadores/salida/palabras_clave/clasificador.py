"""ClasificadorPalabrasClave: clasificación provisional y de respaldo (contexto.md 4.5, PB-21).

Las palabras viven en diccionario.json; aquí solo está el orden de evaluación,
de lo más grave a lo menos grave. Se prefiere el plazo más corto: una palabra de
alarma pesa aunque el texto la niegue, y una persona o la IA afinan después.
id_atributo queda en None: la sección 4.5 solo pide tipo, nivel y área.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radica.aplicacion.puertos.clasificador import ResultadoClasificacion, SolicitudClasificacion
from radica.dominio.valores import NivelRiesgo, TipoPqrs

RUTA_DICCIONARIO = Path(__file__).with_name("diccionario.json")
CONFIANZA_REGLAS = 0.5

# (llave del diccionario, tipo, nivel), en el orden de evaluación de la sección 4.5.
ORDEN_DE_EVALUACION = (
    ("vital", TipoPqrs.RECLAMO, NivelRiesgo.VITAL),
    ("priorizado", TipoPqrs.RECLAMO, NivelRiesgo.PRIORIZADO),
    ("reclamo", TipoPqrs.RECLAMO, NivelRiesgo.SIMPLE),
    ("queja", TipoPqrs.QUEJA, NivelRiesgo.NO_APLICA),
    ("sugerencia", TipoPqrs.SUGERENCIA, NivelRiesgo.NO_APLICA),
    ("solicitud_informacion", TipoPqrs.SOLICITUD_INFORMACION, NivelRiesgo.NO_APLICA),
    ("consulta", TipoPqrs.CONSULTA, NivelRiesgo.NO_APLICA),
)
NIVELES_CON_SENALES = (NivelRiesgo.VITAL, NivelRiesgo.PRIORIZADO)


def normalizar(texto: str) -> str:
    """Texto sin tildes y en minúsculas."""
    return "".join(
        letra
        for letra in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(letra)
    )


@dataclass(frozen=True)
class _Lista:
    """Expresiones tal como están en el diccionario, con su patrón de palabras completas."""

    expresiones: tuple[tuple[str, re.Pattern[str]], ...]

    @classmethod
    def desde(cls, valor: Any, nombre: str) -> "_Lista":
        if not isinstance(valor, list) or not valor or not all(
            isinstance(expresion, str) and expresion.strip() for expresion in valor
        ):
            raise ValueError(f"Diccionario inválido: «{nombre}» debe ser una lista de textos no vacía.")
        return cls(tuple((expresion, _patron(expresion)) for expresion in valor))

    def encontradas(self, texto_normalizado: str) -> tuple[str, ...]:
        return tuple(
            expresion for expresion, patron in self.expresiones if patron.search(texto_normalizado)
        )


def _patron(expresion: str) -> re.Pattern[str]:
    palabras = (re.escape(palabra) for palabra in normalizar(expresion).split())
    return re.compile(r"(?<!\w)" + r"\s+".join(palabras) + r"(?!\w)")


class ClasificadorPalabrasClave:
    """Implementa el puerto ClasificadorPqrs con reglas locales; no llama a ningún servicio.

    Un diccionario inválido falla al construirlo (al arrancar), no al clasificar.
    """

    def __init__(self, ruta_diccionario: Path = RUTA_DICCIONARIO) -> None:
        diccionario = json.loads(ruta_diccionario.read_text(encoding="utf-8"))
        if not isinstance(diccionario, dict) or not diccionario.get("version"):
            raise ValueError("Diccionario inválido: falta «version».")
        self._reglas = tuple(
            (_Lista.desde(diccionario.get(llave), llave), tipo, nivel)
            for llave, tipo, nivel in ORDEN_DE_EVALUACION
        )
        areas = diccionario.get("areas")
        if not isinstance(areas, list) or not areas:
            raise ValueError("Diccionario inválido: «areas» debe ser una lista no vacía.")
        self._areas = tuple(
            (area["id_area"], _Lista.desde(area["palabras"], area["nombre"])) for area in areas
        )

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        texto = normalizar(solicitud.texto_enmascarado)
        tipo, nivel, senales = TipoPqrs.PETICION, NivelRiesgo.NO_APLICA, ()
        for lista, tipo_regla, nivel_regla in self._reglas:
            encontradas = lista.encontradas(texto)
            if encontradas:
                tipo, nivel = tipo_regla, nivel_regla
                senales = encontradas if nivel in NIVELES_CON_SENALES else ()
                break
        return ResultadoClasificacion(
            tipo=tipo,
            id_atributo=None,
            id_area=self._area(texto, solicitud),
            nivel_riesgo=nivel,
            confianza=CONFIANZA_REGLAS,
            senales_riesgo=senales,
        )

    def _area(self, texto: str, solicitud: SolicitudClasificacion) -> int | None:
        vigentes = {area.id for area in solicitud.catalogo.areas}
        for id_area, lista in self._areas:
            if id_area in vigentes and lista.encontradas(texto):
                return id_area
        return None
