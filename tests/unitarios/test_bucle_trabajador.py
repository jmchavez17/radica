"""Ciclo del trabajador con una unidad de trabajo falsa (contexto.md 4.9, decisión D2)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from radica.adaptadores.entrada.trabajador.bucle import Trabajador
from radica.dominio.valores import EstadoIa


class CasoFalso:
    def __init__(self, pendientes: list[int], falla_en: set[int] | None = None) -> None:
        self.pendientes = pendientes
        self.falla_en = falla_en or set()
        self.clasificadas: list[int] = []
        self.con_error: list[int] = []

    def tomar_siguiente(self) -> int | None:
        return self.pendientes[0] if self.pendientes else None

    def ejecutar(self, id_pqrs: int) -> EstadoIa:
        if id_pqrs in self.falla_en:
            raise RuntimeError("texto sensible que no debe ir al registro")
        self.pendientes.remove(id_pqrs)
        self.clasificadas.append(id_pqrs)
        return EstadoIa.COMPLETADA

    def registrar_error_interno(self, id_pqrs: int) -> None:
        self.pendientes.remove(id_pqrs)
        self.con_error.append(id_pqrs)


class Unidades:
    """Cuenta las unidades de trabajo y si cada una se confirmó o se deshizo."""

    def __init__(self, caso: CasoFalso) -> None:
        self.caso = caso
        self.resultados: list[str] = []

    @contextmanager
    def __call__(self) -> Iterator[CasoFalso]:
        try:
            yield self.caso
        except Exception:
            self.resultados.append("deshecha")
            raise
        self.resultados.append("confirmada")


def test_procesa_una_pqrs_por_unidad_de_trabajo() -> None:
    unidades = Unidades(CasoFalso([7, 8]))
    trabajador = Trabajador(unidades)  # type: ignore[arg-type]

    assert trabajador.procesar_una() is True
    assert trabajador.procesar_una() is True
    assert trabajador.procesar_una() is False
    assert unidades.caso.clasificadas == [7, 8]
    assert unidades.resultados == ["confirmada"] * 3


def test_un_error_inesperado_deshace_y_marca_la_pqrs_en_otra_unidad(caplog: pytest.LogCaptureFixture) -> None:
    unidades = Unidades(CasoFalso([7, 8], falla_en={7}))
    trabajador = Trabajador(unidades)  # type: ignore[arg-type]

    with caplog.at_level(logging.INFO, logger="radica.trabajador"):
        assert trabajador.procesar_una() is True
        assert trabajador.procesar_una() is True

    assert unidades.resultados == ["deshecha", "confirmada", "confirmada"]
    assert (unidades.caso.con_error, unidades.caso.clasificadas) == ([7], [8])
    assert "Error inesperado (RuntimeError) al clasificar la PQRS 7" in caplog.text
    assert "texto sensible" not in caplog.text


def test_ejecutar_espera_si_no_hay_pendientes_y_se_detiene() -> None:
    unidades = Unidades(CasoFalso([7]))
    trabajador = Trabajador(unidades, intervalo_s=0.01)  # type: ignore[arg-type]
    esperas = []

    original = trabajador._detenido.wait  # noqa: SLF001

    def esperar(segundos: float) -> bool:
        esperas.append(segundos)
        if len(esperas) == 2:
            trabajador.detener()
        return original(0)

    trabajador._detenido.wait = esperar  # type: ignore[method-assign]  # noqa: SLF001
    trabajador.ejecutar()

    assert unidades.caso.clasificadas == [7]
    assert esperas == [0.01, 0.01]  # no espera después de procesar, sí cuando no hay


def test_un_fallo_de_la_base_no_detiene_el_ciclo(caplog: pytest.LogCaptureFixture) -> None:
    llamadas = []

    @contextmanager
    def unidad_caida() -> Iterator[CasoFalso]:
        llamadas.append(1)
        if len(llamadas) >= 2:
            trabajador.detener()
        raise ConnectionError("la base no responde")
        yield  # pragma: no cover

    trabajador = Trabajador(unidad_caida, intervalo_s=0)  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="radica.trabajador"):
        trabajador.ejecutar()

    assert len(llamadas) == 2
    assert "No se pudo procesar la cola de clasificación (ConnectionError)" in caplog.text
