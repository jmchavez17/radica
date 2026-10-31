"""EnmascaradorReglas: detección por expresiones regulares (contexto.md 4.4, ADR-03).

Los detectores y los valores del peticionario se buscan sobre el texto
«plegado» (sin tildes y en minúsculas), con un mapa de posiciones hacia el
original. Si dos hallazgos se cruzan gana, en este orden: un valor del
peticionario, correo, historia clínica, teléfono y cédula. Se prefiere
enmascarar de más: un valor como «$1.200.000» queda como cédula.
Límite conocido: no detecta nombres de terceros ni direcciones (PB-05).
"""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

from radica.aplicacion.puertos.enmascarador import TextoEnmascarado, Verificacion
from radica.dominio.peticionario import DatosPeticionario

# Un número no empieza ni termina pegado a otros dígitos, ni a «1.» o «,5».
_ANTES = r"(?<!\d)(?<!\d[.,])"
_DESPUES = r"(?!\d)(?![.,]\d)"
_SEP = r"[\s.\-]?"
_PREFIJO_PAIS = r"(?:\+?57" + _SEP + r")?"

CORREO = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}")
HISTORIA_CLINICA = re.compile(
    r"(?<!\w)(?:h\.?\s?c\.?|historia\s+clinica)"
    r"(?:\s*(?:n\.?\s?[o°]\.?|nro\.?|num\.?|numero|#))?"
    r"\s*[:#]?\s*"
    r"(?P<valor>\d(?:[\d.\-]*\d)?)(?!\d)"
)
TELEFONO = re.compile(
    _ANTES
    + _PREFIJO_PAIS
    + r"(?:3\d{2}|\(?60\d\)?)"  # celular de 10 dígitos que empieza por 3, o fijo con indicativo 60X
    + _SEP + r"\d{3}" + _SEP + r"\d{4}"
    + _DESPUES
)
CEDULA = re.compile(_ANTES + r"(?:\d{1,3}(?:\.\d{3}){1,3}|\d{6,10})" + _DESPUES)

_MARCADOR = re.compile(r"\[(?:CEDULA|TELEFONO|CORREO|HC|NOMBRE)_\d+\]")

PRIORIDAD_PETICIONARIO = 0
PRIORIDAD = {"CORREO": 1, "HC": 2, "TELEFONO": 3, "CEDULA": 4}


@dataclass(frozen=True)
class _Hallazgo:
    inicio: int
    fin: int
    tipo: str
    clave: str  # valor normalizado: decide si dos apariciones llevan el mismo marcador
    prioridad: int


def plegar(texto: str) -> tuple[str, list[int]]:
    """Texto sin tildes y en minúsculas, y para cada carácter su posición en el original."""
    plegado: list[str] = []
    origen: list[int] = []
    for posicion, caracter in enumerate(texto):
        for parte in unicodedata.normalize("NFKD", caracter):
            if unicodedata.combining(parte):
                continue
            for letra in parte.casefold():
                plegado.append(letra)
                origen.append(posicion)
    return "".join(plegado), origen


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def _clave_telefono(texto: str) -> str:
    digitos = _digitos(texto)
    return digitos[2:] if len(digitos) == 12 and digitos.startswith("57") else digitos


def _patron_numerico(digitos: str, prefijo: str = "") -> re.Pattern[str]:
    return re.compile(_ANTES + prefijo + _SEP.join(digitos) + _DESPUES)


def _patron_texto(plegado: str) -> re.Pattern[str]:
    palabras = (re.escape(palabra) for palabra in plegado.split())
    return re.compile(r"(?<!\w)" + r"\s+".join(palabras) + r"(?!\w)")


def _patrones_peticionario(datos: DatosPeticionario) -> Iterator[tuple[str, str, re.Pattern[str]]]:
    """(tipo, clave, patrón) de cada valor que dio el peticionario."""
    nombre = " ".join(plegar(datos.nombre)[0].split())
    if nombre:
        yield "NOMBRE", nombre, _patron_texto(nombre)

    documento = datos.numero_documento.strip()
    if re.fullmatch(r"[\d.\s\-]+", documento) and _digitos(documento):
        yield "CEDULA", _digitos(documento), _patron_numerico(_digitos(documento))
    elif documento:
        plegado = plegar(documento)[0]
        yield "CEDULA", plegado, _patron_texto(plegado)

    telefono = _clave_telefono(datos.telefono or "")
    if telefono:
        yield "TELEFONO", telefono, _patron_numerico(telefono, _PREFIJO_PAIS)

    correo = plegar((datos.correo or "").strip())[0]
    if correo:
        yield "CORREO", correo, re.compile(r"(?<![\w.%+\-])" + re.escape(correo) + r"(?![\w\-])")


def _detectar(plegado: str, datos: DatosPeticionario) -> Iterator[tuple[int, int, str, str, int]]:
    """(inicio, fin, tipo, clave, prioridad) sobre el texto plegado, todos, aunque se crucen."""
    for tipo, clave, patron in _patrones_peticionario(datos):
        for encontrado in patron.finditer(plegado):
            yield encontrado.start(), encontrado.end(), tipo, clave, PRIORIDAD_PETICIONARIO
    for encontrado in CORREO.finditer(plegado):
        yield encontrado.start(), encontrado.end(), "CORREO", encontrado.group(), PRIORIDAD["CORREO"]
    for encontrado in HISTORIA_CLINICA.finditer(plegado):
        inicio, fin = encontrado.span("valor")
        yield inicio, fin, "HC", _digitos(encontrado.group("valor")), PRIORIDAD["HC"]
    for encontrado in TELEFONO.finditer(plegado):
        clave = _clave_telefono(encontrado.group())
        yield encontrado.start(), encontrado.end(), "TELEFONO", clave, PRIORIDAD["TELEFONO"]
    for encontrado in CEDULA.finditer(plegado):
        digitos = _digitos(encontrado.group())
        if 6 <= len(digitos) <= 10:
            yield encontrado.start(), encontrado.end(), "CEDULA", digitos, PRIORIDAD["CEDULA"]


def _hallazgos(texto: str, datos: DatosPeticionario) -> list[_Hallazgo]:
    """Hallazgos sin cruces, en orden de aparición y con posiciones del texto original."""
    plegado, origen = plegar(texto)
    candidatos = sorted(
        _detectar(plegado, datos),
        key=lambda c: (c[4], -(c[1] - c[0]), c[0]),
    )
    elegidos: list[_Hallazgo] = []
    for inicio, fin, tipo, clave, prioridad in candidatos:
        if inicio == fin or any(inicio < otro.fin and otro.inicio < fin for otro in elegidos):
            continue
        elegidos.append(_Hallazgo(inicio, fin, tipo, clave, prioridad))

    resultado = []
    for hallazgo in sorted(elegidos, key=lambda h: h.inicio):
        inicio, fin = origen[hallazgo.inicio], origen[hallazgo.fin - 1] + 1
        while fin < len(texto) and unicodedata.combining(texto[fin]):
            fin += 1
        resultado.append(_Hallazgo(inicio, fin, hallazgo.tipo, hallazgo.clave, hallazgo.prioridad))
    return resultado


class EnmascaradorReglas:
    """Implementa el puerto Enmascarador con reglas; no llama a ningún servicio."""

    def enmascarar(self, texto: str, datos: DatosPeticionario) -> TextoEnmascarado:
        numeros: dict[tuple[str, str], str] = {}
        contadores: dict[str, int] = {}
        partes: list[str] = []
        previo = 0
        for hallazgo in _hallazgos(texto, datos):
            llave = (hallazgo.tipo, hallazgo.clave)
            if llave not in numeros:
                contadores[hallazgo.tipo] = contadores.get(hallazgo.tipo, 0) + 1
                numeros[llave] = f"{hallazgo.tipo}_{contadores[hallazgo.tipo]}"
            partes += [texto[previo : hallazgo.inicio], f"[{numeros[llave]}]"]
            previo = hallazgo.fin
        partes.append(texto[previo:])
        return TextoEnmascarado("".join(partes), tuple(numeros.values()))

    def verificar(self, texto_enmascarado: str, datos: DatosPeticionario) -> Verificacion:
        # Los marcadores llevan dígitos («_1»): se quitan antes de volver a buscar.
        sin_marcadores = _MARCADOR.sub(" ", texto_enmascarado)
        tipos = sorted({hallazgo.tipo for hallazgo in _hallazgos(sin_marcadores, datos)})
        return Verificacion(limpio=not tipos, tipos_detectados=tuple(tipos))
