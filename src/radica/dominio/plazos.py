"""Selección del término legal y cálculo del vencimiento (contexto.md 4.6, ADR-02).

Todo es puro: el término y los festivos llegan como parámetros, así que se
prueba sin base de datos. Las fechas se manejan con zona horaria y el conteo se
hace en hora de Colombia.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from radica.dominio.valores import NivelRiesgo, Poblacion, Regimen, TipoPqrs, Unidad

ZONA_COLOMBIA = ZoneInfo("America/Bogota")
CIERRE_DEL_DIA = time(23, 59, 59)

NOMBRES_TIPO = {
    TipoPqrs.PETICION: "Petición",
    TipoPqrs.QUEJA: "Queja",
    TipoPqrs.RECLAMO: "Reclamo",
    TipoPqrs.SUGERENCIA: "Sugerencia",
    TipoPqrs.SOLICITUD_INFORMACION: "Solicitud de información",
    TipoPqrs.CONSULTA: "Consulta",
}


class TerminoNoConfigurado(Exception):
    """No hay un único término vigente para la clasificación: es un error de configuración."""


@dataclass(frozen=True)
class Termino:
    """Fila de termino_legal."""

    id: int
    regimen: Regimen
    tipo_pqrs: TipoPqrs
    nivel_riesgo: NivelRiesgo
    poblacion: Poblacion
    valor: int
    unidad: Unidad
    id_calendario: int | None
    fuente_normativa: str
    vigente_desde: date
    vigente_hasta: date | None = None

    def vigente_en(self, dia: date) -> bool:
        return self.vigente_desde <= dia and (self.vigente_hasta is None or dia <= self.vigente_hasta)

    @property
    def regla(self) -> str:
        """Texto de la regla para la API, como lo lista docs/modelo-datos.md 2.3."""
        descripcion = NOMBRES_TIPO[self.tipo_pqrs]
        if self.regimen is Regimen.SALUD:
            descripcion += " en salud"
        if self.nivel_riesgo is not NivelRiesgo.NO_APLICA:
            descripcion += f", riesgo {self.nivel_riesgo.value.lower()}"
        if self.poblacion is Poblacion.MENOR:
            descripcion += ", paciente menor de edad"
        if self.unidad is Unidad.DIAS_HABILES:
            plazo = f"{self.valor} días hábiles"
        elif self.poblacion is Poblacion.MENOR:
            # modelo-datos.md escribe «8 horas» para este término, sin «corridas».
            plazo = f"{self.valor} horas"
        else:
            plazo = f"{self.valor} horas corridas"
        return f"{descripcion}: {plazo}"


def nivel_efectivo(tipo: TipoPqrs, nivel: NivelRiesgo) -> NivelRiesgo:
    """Un RECLAMO nunca queda con NO_APLICA: el mínimo es SIMPLE.

    Los demás tipos conservan el nivel que traen; su término no depende de él.
    """
    if tipo is TipoPqrs.RECLAMO and nivel is NivelRiesgo.NO_APLICA:
        return NivelRiesgo.SIMPLE
    return nivel


def dia_en_colombia(momento: datetime) -> date:
    return momento.astimezone(ZONA_COLOMBIA).date()


def seleccionar_termino(
    terminos: Iterable[Termino],
    tipo: TipoPqrs,
    nivel: NivelRiesgo,
    paciente_menor: bool,
    fecha_radicacion: datetime,
) -> Termino:
    """Término vigente a la fecha de radicación para la clasificación dada.

    RECLAMO: por tipo, nivel y población; MENOR solo con VITAL y paciente
    menor. Si no hay término MENOR vigente (antes del 2026-06-09) se aplica
    el de TODAS, como se aprobó en la sesión 2. Otros tipos: solo por tipo.
    """
    dia = dia_en_colombia(fecha_radicacion)
    vigentes = [termino for termino in terminos if termino.vigente_en(dia)]
    nivel = nivel_efectivo(tipo, nivel)

    def candidatos(poblacion: Poblacion) -> list[Termino]:
        return [
            termino
            for termino in vigentes
            if termino.tipo_pqrs is tipo
            and termino.poblacion is poblacion
            and (tipo is not TipoPqrs.RECLAMO or termino.nivel_riesgo is nivel)
        ]

    poblacion = (
        Poblacion.MENOR
        if tipo is TipoPqrs.RECLAMO and nivel is NivelRiesgo.VITAL and paciente_menor
        else Poblacion.TODAS
    )
    encontrados = candidatos(poblacion)
    if not encontrados and poblacion is Poblacion.MENOR:
        poblacion = Poblacion.TODAS
        encontrados = candidatos(poblacion)
    if len(encontrados) != 1:
        raise TerminoNoConfigurado(
            f"Hay {len(encontrados)} términos vigentes el {dia.isoformat()} para"
            f" {tipo.value}, {nivel.value}, {poblacion.value}; se esperaba exactamente uno."
        )
    return encontrados[0]


class CalculadoraDePlazos:
    """Calcula el vencimiento de un término (SUPUESTO de conteo, validar en V3 y V4).

    DIAS_HABILES: cuenta desde el día hábil siguiente al de radicación, sin
    importar la hora; son hábiles los lunes a viernes que no son festivo del
    calendario del término. Vence a las 23:59:59, hora de Colombia.
    HORAS_CORRIDAS: radicación + N horas, sin descontar festivos ni fines de semana.
    """

    def calcular(
        self, termino: Termino, fecha_radicacion: datetime, festivos: Collection[date]
    ) -> datetime:
        if fecha_radicacion.tzinfo is None:
            raise ValueError("La fecha de radicación debe tener zona horaria.")
        if termino.unidad is Unidad.HORAS_CORRIDAS:
            limite = fecha_radicacion.astimezone(UTC) + timedelta(hours=termino.valor)
            return limite.astimezone(ZONA_COLOMBIA)
        dia = dia_en_colombia(fecha_radicacion)
        contados = 0
        while contados < termino.valor:
            dia += timedelta(days=1)
            if dia.weekday() < 5 and dia not in festivos:
                contados += 1
        return datetime.combine(dia, CIERRE_DEL_DIA, tzinfo=ZONA_COLOMBIA)
