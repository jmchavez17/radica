"""Puerto AuditoriaRepository (Entrega 2, 5.3; contexto.md 4.12).

registrar_llamada_ia queda para la sesión de AdaptadorClaude.
"""

from typing import Protocol

from radica.dominio.pqrs import EventoAuditoria


class AuditoriaRepository(Protocol):
    def registrar(self, evento: EventoAuditoria) -> None:
        """Inserta el evento; la tabla es de solo inserción."""
        ...

    def historial(self, id_pqrs: int) -> list[EventoAuditoria]:
        """Eventos de la PQRS en orden cronológico."""
        ...
