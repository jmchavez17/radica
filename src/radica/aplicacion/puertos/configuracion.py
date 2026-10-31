"""Puerto ConfiguracionRepository (Entrega 2, 5.3).

Diferencias con la sección 5.3: festivos() devuelve todos los del calendario,
porque un término en días hábiles puede cruzar el año (caso 6 de 4.6), y
catalogo() reúne áreas() y atributos() en el Catalogo del clasificador.
"""

from datetime import date
from typing import Protocol

from radica.aplicacion.puertos.clasificador import Catalogo
from radica.dominio.plazos import Termino


class ConfiguracionRepository(Protocol):
    def terminos_vigentes(self, dia: date) -> tuple[Termino, ...]: ...

    def festivos(self, id_calendario: int) -> frozenset[date]: ...

    def catalogo(self) -> Catalogo:
        """Tipos, atributos y áreas activos."""
        ...
