"""Datos personales del peticionario (contexto.md 4.2)."""

from dataclasses import dataclass, field

from radica.dominio.valores import TipoDocumento


@dataclass(frozen=True)
class DatosPeticionario:
    """Datos tal como llegan del formulario.

    Solo se usan para cifrarlos, calcular el HMAC del documento y enmascarar el
    texto. Nunca salen en repr(), en los registros ni en la API.
    """

    tipo_documento: TipoDocumento
    numero_documento: str = field(repr=False)
    nombre: str = field(repr=False)
    telefono: str | None = field(default=None, repr=False)
    correo: str | None = field(default=None, repr=False)
