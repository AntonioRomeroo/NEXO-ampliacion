import csv

import pytest

from dominio.excepciones import ErrorPersistencia
from persistencia.registro_tokens import RegistroTokens


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "datos" / "uso_llm.csv"


def test_resumen_vacio(ruta):
    assert RegistroTokens(ruta).resumen() == {"peticiones": 0, "tokens_entrada": 0, "tokens_salida": 0, "coste": 0.0}


def test_cabecera_unica_y_acumulacion(ruta):
    RegistroTokens(ruta).registrar("hola", 10, 5)
    RegistroTokens(ruta).registrar("adiós", 8, 3)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 3 and lineas[0] == "fecha,pregunta,tokens_entrada,tokens_salida,coste"


def test_el_coste_sigue_la_formula(ruta):
    RegistroTokens(ruta).registrar("hola", 10, 500)
    with open(ruta, newline="", encoding="utf-8") as f:
        fila = next(csv.DictReader(f))
    assert fila["tokens_salida"] == "500" and float(fila["coste"]) == pytest.approx(500 * 0.008 / 1000)


def test_precio_personalizado(ruta):
    assert RegistroTokens(ruta, precio_por_1000=2).calcular_coste(1000) == 2


def test_tokens_desconocidos_cuentan_como_cero(ruta):
    RegistroTokens(ruta).registrar("hola", None, None)
    assert RegistroTokens(ruta).resumen()["tokens_salida"] == 0


def test_resumen_suma_todo(ruta):
    registro = RegistroTokens(ruta)
    registro.registrar("a", 10, 1000)
    registro.registrar("b", 20, 2000)
    assert registro.resumen() == {"peticiones": 2, "tokens_entrada": 30, "tokens_salida": 3000,
                                  "coste": pytest.approx(3000 * 0.008 / 1000)}


def test_la_pregunta_con_comas_y_saltos_de_linea_no_rompe_el_csv(ruta):
    registro = RegistroTokens(ruta)
    registro.registrar("hola, qué tal\nbien?", 1, 1)
    assert registro.resumen()["peticiones"] == 1


def test_error_al_escribir(tmp_path):
    with pytest.raises(ErrorPersistencia):
        RegistroTokens(tmp_path).registrar("hola", 1, 1)  # la ruta es una carpeta
