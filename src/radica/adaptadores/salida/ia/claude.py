"""AdaptadorClaude: el puerto ClasificadorPqrs sobre la API de Anthropic (contexto.md 4.9, Entrega 2 9.4).

- SDK oficial `anthropic`. Sus reintentos están apagados (max_retries=0): los
  reintentos son los de 4.9. Tiempo agotado, 429, 5xx o un error de conexión:
  hasta 2 reintentos con esperas de 2 y 8 s. 401 y 403: CREDENCIAL_INVALIDA,
  sin reintento. 400 y demás 4xx: ERROR_PROVEEDOR, sin reintento. Salida
  inválida: un reintento. Nunca más de 3 intentos.
- Sin temperature: Claude Haiku 5.5 y la versión 2026-10-21 de la API la
  rechazan con 400 (decisión D5 de la sesión 4). La forma de la salida la fija
  el esquema de salidas estructuradas; thinking va desactivado y effort en
  low, para que los 400 tokens de salida sean para el JSON.
- El texto va delimitado como dato entre <pqrs> y </pqrs> (LLM01). El modelo
  no tiene herramientas. Las instrucciones son un archivo versionado de
  instrucciones/.
- La salida se valida completa con Pydantic y contra el catálogo de la
  solicitud; si algo no cumple no se aplica nada (SalidaInvalida).
- No guarda nada: devuelve cada intento en UsoIA para que el caso de uso lo
  registre en llamada_ia, sin el texto enviado ni la respuesta.
"""

import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Protocol

import anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from radica.aplicacion.puertos.clasificador import (
    Catalogo,
    ProveedorNoDisponible,
    ResultadoClasificacion,
    SalidaInvalida,
    SolicitudClasificacion,
    UsoIA,
)
from radica.dominio.valores import NivelRiesgo, ResultadoLlamadaIA, TipoPqrs

registro = logging.getLogger("radica.ia")

PROVEEDOR = "anthropic"
CARPETA_INSTRUCCIONES = Path(__file__).with_name("instrucciones")
MAXIMO_TOKENS_SALIDA = 400
MAXIMO_INTENTOS = 3
ESPERAS_S = (2.0, 8.0)  # antes del primer y del segundo reintento por error transitorio
MAXIMO_RESUMEN = 200
UN_MILLON = Decimal(1_000_000)
CENTAVOS_DE_COSTO = Decimal("0.000001")  # llamada_ia.costo_usd es NUMERIC(10,6)
_ETIQUETA_PQRS = re.compile(r"<\s*/?\s*pqrs\s*>", re.IGNORECASE)


class _DatoClave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str
    valor: str


# Esquema de la respuesta del modelo. datosClave va como lista de pares: las
# salidas estructuradas exigen objetos con propiedades fijas, así que un
# diccionario libre no se puede pedir. Sin docstring, para que no viaje al modelo.
class SalidaClaude(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoPqrs
    idAtributo: int | None
    idArea: int | None
    nivelRiesgo: NivelRiesgo
    confianza: float = Field(ge=0, le=1)
    senalesRiesgo: list[str]
    resumen: str = Field(max_length=MAXIMO_RESUMEN)
    datosClave: list[_DatoClave]


def _sin_notas_internas(esquema: Any) -> Any:
    """Quita títulos y descripciones generados desde el código (docstrings de los enums).

    Las restricciones que el API no admite (mínimo, máximo, longitud) quedan en
    la descripción que les pone transform_schema, y Pydantic las valida después.
    """
    if isinstance(esquema, list):
        return [_sin_notas_internas(parte) for parte in esquema]
    if not isinstance(esquema, dict):
        return esquema
    limpio = {}
    for llave, valor in esquema.items():
        if llave == "title":
            continue
        if llave == "description" and not str(valor).startswith("{"):
            continue
        limpio[llave] = valor if llave in ("enum", "required") else _sin_notas_internas(valor)
    return limpio


ESQUEMA_SALIDA = _sin_notas_internas(anthropic.transform_schema(SalidaClaude))


class _Mensajes(Protocol):
    def create(self, **parametros: Any) -> Any: ...


class ClienteMensajes(Protocol):
    """Lo que el adaptador usa del cliente del SDK; las pruebas pasan uno falso, sin red."""

    @property
    def messages(self) -> _Mensajes: ...


class _NoValida(Exception):
    """La respuesta llegó pero no se puede aplicar; el mensaje no repite su contenido."""


@dataclass(frozen=True)
class _Fallo:
    resultado: ResultadoLlamadaIA
    reintentable: bool


def cargar_instrucciones(carpeta: Path = CARPETA_INSTRUCCIONES) -> dict[str, str]:
    """{versión: texto} de cada archivo <versión>.md de la carpeta."""
    return {archivo.stem: archivo.read_text(encoding="utf-8") for archivo in sorted(carpeta.glob("*.md"))}


def texto_del_catalogo(catalogo: Catalogo) -> str:
    lineas = ["## Catálogo vigente", "", "Tipos: " + ", ".join(tipo.value for tipo in catalogo.tipos)]
    lineas.append("Niveles de riesgo: " + ", ".join(nivel.value for nivel in NivelRiesgo))
    lineas += ["", "Atributos de calidad (id: nombre. definición):"]
    lineas += [f"- {a.id}: {a.nombre}. {a.definicion}" for a in catalogo.atributos]
    lineas += ["", "Áreas (id: nombre):"]
    lineas += [f"- {area.id}: {area.nombre}" for area in catalogo.areas]
    return "\n".join(lineas)


def delimitar(texto_enmascarado: str) -> str:
    """El texto como dato; una etiqueta <pqrs> escrita en el texto no puede cerrar el delimitador."""
    return "<pqrs>\n" + _ETIQUETA_PQRS.sub("[etiqueta eliminada]", texto_enmascarado) + "\n</pqrs>"


def _fallo(error: anthropic.AnthropicError) -> _Fallo:
    if isinstance(error, anthropic.APITimeoutError):
        return _Fallo(ResultadoLlamadaIA.TIMEOUT, True)
    if isinstance(error, anthropic.RateLimitError):
        return _Fallo(ResultadoLlamadaIA.LIMITE_CUOTA, True)
    if isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return _Fallo(ResultadoLlamadaIA.CREDENCIAL_INVALIDA, False)
    if isinstance(error, anthropic.APIStatusError):
        return _Fallo(ResultadoLlamadaIA.ERROR_PROVEEDOR, error.status_code >= 500)
    if isinstance(error, anthropic.APIConnectionError):
        return _Fallo(ResultadoLlamadaIA.ERROR_PROVEEDOR, True)
    return _Fallo(ResultadoLlamadaIA.ERROR_PROVEEDOR, False)


class AdaptadorClaude:
    """Implementa el puerto ClasificadorPqrs con Claude. Solo lanza ProveedorNoDisponible o SalidaInvalida."""

    def __init__(
        self,
        cliente: ClienteMensajes,
        modelo: str,
        precio_entrada_usd_mtok: Decimal,
        precio_salida_usd_mtok: Decimal,
        instrucciones: dict[str, str] | None = None,
        esperar: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cliente = cliente
        self._modelo = modelo
        self._precio_entrada = precio_entrada_usd_mtok
        self._precio_salida = precio_salida_usd_mtok
        self._instrucciones = instrucciones if instrucciones is not None else cargar_instrucciones()
        self._esperar = esperar
        self._reloj = reloj

    @classmethod
    def con_clave(
        cls,
        api_key: str,
        modelo: str,
        timeout_s: float,
        precio_entrada_usd_mtok: Decimal,
        precio_salida_usd_mtok: Decimal,
    ) -> "AdaptadorClaude":
        cliente = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=0)
        return cls(cliente, modelo, precio_entrada_usd_mtok, precio_salida_usd_mtok)

    def clasificar(self, solicitud: SolicitudClasificacion) -> ResultadoClasificacion:
        instrucciones = self._instrucciones.get(solicitud.version_instrucciones)
        if instrucciones is None:
            raise ProveedorNoDisponible(
                f"No hay instrucciones {solicitud.version_instrucciones} en el adaptador."
            )
        parametros = {
            "model": self._modelo,
            "max_tokens": MAXIMO_TOKENS_SALIDA,
            "system": instrucciones.rstrip() + "\n\n" + texto_del_catalogo(solicitud.catalogo),
            "messages": [{"role": "user", "content": delimitar(solicitud.texto_enmascarado)}],
            "thinking": {"type": "disabled"},
            "output_config": {
                "effort": "low",
                "format": {"type": "json_schema", "schema": ESQUEMA_SALIDA},
            },
        }

        fallidos: list[UsoIA] = []
        transitorios = invalidas = 0
        for intento in range(1, MAXIMO_INTENTOS + 1):
            inicio = self._reloj()
            try:
                respuesta = self._cliente.messages.create(**parametros)
            except anthropic.AnthropicError as error:
                fallo = _fallo(error)
                fallidos.append(self._uso(intento, fallo.resultado, inicio))
                registro.warning("Intento %d de clasificación sin respuesta: %s", intento, fallo.resultado)
                if fallo.reintentable and transitorios < len(ESPERAS_S) and intento < MAXIMO_INTENTOS:
                    self._esperar(ESPERAS_S[transitorios])
                    transitorios += 1
                    continue
                raise ProveedorNoDisponible(
                    f"El proveedor no respondió ({fallo.resultado.value}).", tuple(fallidos)
                ) from None

            entrada, salida = respuesta.usage.input_tokens, respuesta.usage.output_tokens
            try:
                resultado = self._resultado(respuesta, solicitud.catalogo)
            except _NoValida as error:
                fallidos.append(
                    self._uso(intento, ResultadoLlamadaIA.SALIDA_INVALIDA, inicio, entrada, salida)
                )
                registro.warning("Intento %d de clasificación con salida inválida: %s", intento, error)
                if invalidas < 1 and intento < MAXIMO_INTENTOS:
                    invalidas += 1
                    continue
                raise SalidaInvalida(f"La salida no cumple el esquema: {error}", tuple(fallidos)) from None

            uso = self._uso(intento, ResultadoLlamadaIA.OK, inicio, entrada, salida)
            return ResultadoClasificacion(
                tipo=resultado.tipo,
                id_atributo=resultado.idAtributo,
                id_area=resultado.idArea,
                nivel_riesgo=resultado.nivelRiesgo,
                confianza=resultado.confianza,
                resumen=resultado.resumen.strip() or None,
                datos_clave={dato.nombre: dato.valor for dato in resultado.datosClave},
                senales_riesgo=tuple(resultado.senalesRiesgo),
                uso=uso,
                intentos_fallidos=tuple(fallidos),
            )
        raise AssertionError("inalcanzable: el último intento siempre devuelve o lanza")  # pragma: no cover

    def costo(self, tokens_entrada: int, tokens_salida: int) -> Decimal:
        """tokens × precio por millón, redondeado a 6 decimales como llamada_ia.costo_usd."""
        bruto = (tokens_entrada * self._precio_entrada + tokens_salida * self._precio_salida) / UN_MILLON
        return bruto.quantize(CENTAVOS_DE_COSTO, rounding=ROUND_HALF_UP)

    def _uso(
        self,
        intento: int,
        resultado: ResultadoLlamadaIA,
        inicio: float,
        tokens_entrada: int = 0,
        tokens_salida: int = 0,
    ) -> UsoIA:
        return UsoIA(
            proveedor=PROVEEDOR,
            modelo=self._modelo,
            tokens_entrada=tokens_entrada,
            tokens_salida=tokens_salida,
            costo_usd=self.costo(tokens_entrada, tokens_salida),
            latencia_ms=max(0, round((self._reloj() - inicio) * 1000)),
            intento=intento,
            resultado=resultado,
        )

    def _resultado(self, respuesta: Any, catalogo: Catalogo) -> SalidaClaude:
        if respuesta.stop_reason != "end_turn":
            raise _NoValida(f"la respuesta terminó con stop_reason={respuesta.stop_reason}")
        textos: Sequence[str] = [bloque.text for bloque in respuesta.content if bloque.type == "text"]
        if len(textos) != 1:
            raise _NoValida(f"se esperaba un bloque de texto y llegaron {len(textos)}")
        try:
            salida = SalidaClaude.model_validate_json(textos[0])
        except ValidationError as error:
            campos = sorted({".".join(str(parte) for parte in e["loc"]) or "raíz" for e in error.errors()})
            raise _NoValida("campos inválidos: " + ", ".join(campos)) from None
        if salida.tipo not in catalogo.tipos:
            raise _NoValida("tipo fuera del catálogo")
        if salida.idAtributo is not None and salida.idAtributo not in {a.id for a in catalogo.atributos}:
            raise _NoValida("idAtributo fuera del catálogo")
        if salida.idArea is not None and salida.idArea not in {area.id for area in catalogo.areas}:
            raise _NoValida("idArea fuera del catálogo")
        return salida
