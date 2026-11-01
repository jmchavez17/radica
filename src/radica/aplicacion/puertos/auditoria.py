"""Puerto AuditoriaRepository (Entrega 2, 5.3; contexto.md 4.9 y 4.12).

registrar_llamada_ia guarda en llamada_ia los metadatos de un intento, nunca
el texto enviado ni la respuesta. El historial muestra modelo y versión de
instrucciones en los eventos de la IA tomándolos de esa tabla (decisión D3
de la sesión 4, sin columnas nuevas en auditoria).
"""

from typing import Protocol

from radica.aplicacion.puertos.clasificador import UsoIA
from radica.dominio.pqrs import EventoAuditoria


class AuditoriaRepository(Protocol):
    def registrar(self, evento: EventoAuditoria) -> None:
        """Inserta el evento; la tabla es de solo inserción."""
        ...

    def historial(self, id_pqrs: int) -> list[EventoAuditoria]:
        """Eventos de la PQRS en orden cronológico."""
        ...

    def registrar_llamada_ia(self, id_pqrs: int, uso: UsoIA, version_instrucciones: str) -> int:
        """Inserta una fila de llamada_ia (operación CLASIFICAR) y devuelve su id."""
        ...
