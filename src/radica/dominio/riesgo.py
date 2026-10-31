"""Política de riesgo: la IA puede subir el riesgo o acortar el plazo, nunca lo contrario.

RNF-07 y ADR-02, con la precisión de contexto.md 4.9. Es pura: recibe la
clasificación vigente y la sugerida, cada una con el vencimiento que le
calculó la CalculadoraDePlazos. Además del vencimiento compara la gravedad
(decisión D7 de la sesión 4): una sugerencia que bajaría el nivel no se
aplica aunque el plazo quede igual.
"""

from dataclasses import dataclass
from datetime import datetime

from radica.dominio.plazos import nivel_efectivo
from radica.dominio.valores import EstadoPqrs, NivelRiesgo, TipoPqrs

GRAVEDAD = {
    NivelRiesgo.NO_APLICA: 0,
    NivelRiesgo.SIMPLE: 1,
    NivelRiesgo.PRIORIZADO: 2,
    NivelRiesgo.VITAL: 3,
}
NIVELES_SOLO_DE_RECLAMO = (NivelRiesgo.PRIORIZADO, NivelRiesgo.VITAL)


@dataclass(frozen=True)
class ClasificacionConPlazo:
    tipo: TipoPqrs
    nivel_riesgo: NivelRiesgo
    fecha_vencimiento: datetime


@dataclass(frozen=True)
class DecisionDeRiesgo:
    """aplicar: la sugerencia queda vigente. motivo explica la revisión, si la pide."""

    aplicar: bool
    estado: EstadoPqrs
    motivo: str | None = None

    @property
    def requiere_revision(self) -> bool:
        return self.estado is EstadoPqrs.REQUIERE_REVISION


def _formato(numero: float) -> str:
    return f"{numero:.2f}".replace(".", ",")


class PoliticaDeRiesgo:
    """Decide si una sugerencia de la IA se aplica y si la PQRS necesita revisión humana."""

    def __init__(self, umbral_confianza: float) -> None:
        if not 0 < umbral_confianza < 1:
            raise ValueError("El umbral de confianza debe estar entre 0 y 1.")
        self._umbral = umbral_confianza

    def decidir(
        self, vigente: ClasificacionConPlazo, sugerida: ClasificacionConPlazo, confianza: float
    ) -> DecisionDeRiesgo:
        nivel_vigente = nivel_efectivo(vigente.tipo, vigente.nivel_riesgo)
        nivel_sugerido = nivel_efectivo(sugerida.tipo, sugerida.nivel_riesgo)

        if sugerida.fecha_vencimiento > vigente.fecha_vencimiento:
            return DecisionDeRiesgo(
                False, EstadoPqrs.REQUIERE_REVISION, "La sugerencia de la IA alargaría el plazo vigente."
            )
        if GRAVEDAD[nivel_sugerido] < GRAVEDAD[nivel_vigente]:
            return DecisionDeRiesgo(
                False,
                EstadoPqrs.REQUIERE_REVISION,
                "La sugerencia de la IA bajaría el nivel de riesgo vigente.",
            )

        motivos = []
        if confianza < self._umbral:
            motivos.append(
                f"Confianza {_formato(confianza)} menor al umbral {_formato(self._umbral)}."
            )
        if nivel_sugerido in NIVELES_SOLO_DE_RECLAMO and sugerida.tipo is not TipoPqrs.RECLAMO:
            motivos.append(
                f"La IA marcó riesgo {nivel_sugerido.value} en un tipo distinto de RECLAMO."
            )
        if motivos:
            return DecisionDeRiesgo(True, EstadoPqrs.REQUIERE_REVISION, " ".join(motivos))
        return DecisionDeRiesgo(True, EstadoPqrs.CLASIFICADA)
