"""EnmascaradorReglas (contexto.md 4.4, HU-03). Todos los datos son sintéticos."""

import pytest

from radica.adaptadores.salida.enmascarador.reglas import EnmascaradorReglas
from radica.dominio.peticionario import DatosPeticionario
from radica.dominio.valores import TipoDocumento

SIN_DATOS = DatosPeticionario(TipoDocumento.CC, "", "")
PETICIONARIO = DatosPeticionario(
    TipoDocumento.CC, "1000000001", "Usuario Sintético Uno", "3000000000", "usuario1@ejemplo.com"
)


@pytest.fixture
def enmascarador() -> EnmascaradorReglas:
    return EnmascaradorReglas()


def _enmascarar(enmascarador: EnmascaradorReglas, texto: str, datos: DatosPeticionario = SIN_DATOS) -> str:
    return enmascarador.enmascarar(texto, datos).texto


def test_hu03_cedula_telefono_y_correo_quedan_con_marcadores(enmascarador: EnmascaradorReglas) -> None:
    texto = "Soy la cédula 52123456, mi celular es 3101234567 y mi correo es tercero@ejemplo.com."

    resultado = enmascarador.enmascarar(texto, SIN_DATOS)

    assert resultado.texto == (
        "Soy la cédula [CEDULA_1], mi celular es [TELEFONO_1] y mi correo es [CORREO_1]."
    )
    assert resultado.marcadores == ("CEDULA_1", "TELEFONO_1", "CORREO_1")
    for valor in ("52123456", "3101234567", "tercero@ejemplo.com"):
        assert valor not in resultado.texto


def test_ejemplo_del_contrato(enmascarador: EnmascaradorReglas) -> None:
    texto = (
        "Desde hace tres semanas me ordenaron una resonancia y no me han dado la autorización."
        " Llamé dos veces y nadie responde. Mi teléfono es 3000000000."
    )
    assert _enmascarar(enmascarador, texto, PETICIONARIO).endswith("Mi teléfono es [TELEFONO_1].")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("cédula 1.000.000.001 del titular", "cédula [CEDULA_1] del titular"),
        ("documento 123.456 de prueba", "documento [CEDULA_1] de prueba"),
        ("TI 1234567890 del hijo", "TI [CEDULA_1] del hijo"),
        ("número 12345 y 12345678901", "número 12345 y 12345678901"),
    ],
    ids=["con-puntos", "seis-digitos", "diez-digitos", "fuera-de-rango"],
)
def test_documentos_de_6_a_10_digitos(enmascarador: EnmascaradorReglas, texto: str, esperado: str) -> None:
    assert _enmascarar(enmascarador, texto) == esperado


@pytest.mark.parametrize(
    "telefono",
    ["3101234567", "310 123 4567", "310-123-4567", "+57 3101234567", "6021234567", "(602) 123 4567"],
)
def test_telefonos_colombianos(enmascarador: EnmascaradorReglas, telefono: str) -> None:
    assert _enmascarar(enmascarador, f"Llamar al {telefono} en la tarde") == "Llamar al [TELEFONO_1] en la tarde"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("HC 123456 del paciente", "HC [HC_1] del paciente"),
        ("H.C. 123456", "H.C. [HC_1]"),
        ("historia clínica n.º 123456", "historia clínica n.º [HC_1]"),
        ("Historia Clinica No. 1234", "Historia Clinica No. [HC_1]"),
        ("historia clínica número 98765432", "historia clínica número [HC_1]"),
        ("HC: 55", "HC: [HC_1]"),
    ],
)
def test_historia_clinica(enmascarador: EnmascaradorReglas, texto: str, esperado: str) -> None:
    assert _enmascarar(enmascarador, texto) == esperado


def test_el_mismo_valor_recibe_el_mismo_marcador(enmascarador: EnmascaradorReglas) -> None:
    texto = "Llamen al 3101234567 o al 310 123 4567; si no, al 3209876543. HC 1234, cédula 1.234.567 y 1234567."

    resultado = enmascarador.enmascarar(texto, SIN_DATOS)

    assert resultado.texto == (
        "Llamen al [TELEFONO_1] o al [TELEFONO_1]; si no, al [TELEFONO_2]."
        " HC [HC_1], cédula [CEDULA_1] y [CEDULA_1]."
    )
    assert resultado.marcadores == ("TELEFONO_1", "TELEFONO_2", "HC_1", "CEDULA_1")


def test_el_nombre_del_formulario_sin_importar_mayusculas_ni_tildes(enmascarador: EnmascaradorReglas) -> None:
    texto = "Yo, USUARIO SINTETICO UNO, y luego usuario  sintético uno otra vez."
    assert _enmascarar(enmascarador, texto, PETICIONARIO) == "Yo, [NOMBRE_1], y luego [NOMBRE_1] otra vez."


def test_el_nombre_no_corta_otras_palabras(enmascarador: EnmascaradorReglas) -> None:
    datos = DatosPeticionario(TipoDocumento.CC, "1000000001", "Ana")
    assert _enmascarar(enmascarador, "Ana pidió una cita con Mariana y Anabel.", datos) == (
        "[NOMBRE_1] pidió una cita con Mariana y Anabel."
    )


def test_los_valores_del_peticionario_aunque_las_reglas_no_los_detecten(
    enmascarador: EnmascaradorReglas,
) -> None:
    datos = DatosPeticionario(TipoDocumento.PA, "AB12345", "Usuario Sintético Dos", "4441234", "u2@ejemplo.test")
    texto = "Pasaporte ab12345, fijo 444 1234, correo U2@Ejemplo.TEST."
    assert _enmascarar(enmascarador, texto, datos) == (
        "Pasaporte [CEDULA_1], fijo [TELEFONO_1], correo [CORREO_1]."
    )


def test_el_documento_del_peticionario_con_puntos_es_el_mismo_marcador(
    enmascarador: EnmascaradorReglas,
) -> None:
    texto = "Mi cédula es 1.000.000.001 (1000000001) y la de mi madre 41234567."
    assert _enmascarar(enmascarador, texto, PETICIONARIO) == (
        "Mi cédula es [CEDULA_1] ([CEDULA_1]) y la de mi madre [CEDULA_2]."
    )


def test_texto_sin_datos_queda_igual(enmascarador: EnmascaradorReglas) -> None:
    texto = "La cita del 30 de octubre a las 16:00 se canceló dos veces."
    resultado = enmascarador.enmascarar(texto, PETICIONARIO)
    assert (resultado.texto, resultado.marcadores) == (texto, ())


def test_verificar_un_texto_enmascarado(enmascarador: EnmascaradorReglas) -> None:
    texto = "Soy Usuario Sintético Uno, cédula 1000000001, HC 123456, escribo a usuario1@ejemplo.com."
    enmascarado = enmascarador.enmascarar(texto, PETICIONARIO).texto

    assert enmascarador.verificar(enmascarado, PETICIONARIO).limpio


def test_verificar_detecta_lo_que_quedo_sin_devolver_valores(enmascarador: EnmascaradorReglas) -> None:
    verificacion = enmascarador.verificar(
        "[NOMBRE_1] llamó desde el 3101234567; lo atendió usuario sintético uno.", PETICIONARIO
    )

    assert not verificacion.limpio
    assert verificacion.tipos_detectados == ("NOMBRE", "TELEFONO")
    assert "3101234567" not in repr(verificacion)


def test_los_datos_del_peticionario_no_salen_en_repr() -> None:
    texto = repr(PETICIONARIO)
    for valor in ("1000000001", "Usuario", "3000000000", "usuario1@"):
        assert valor not in texto
