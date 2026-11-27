import pytest

from dominio.excepciones import ErrorPersistencia
from persistencia.registro_transcripciones import RegistroTranscripciones


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "datos" / "transcripciones.csv"


def test_resumen_vacio(ruta):
    assert RegistroTranscripciones(ruta).resumen() == {
        "transcripciones": 0, "segundos_audio": 0.0, "milisegundos": 0.0}


def test_cabecera_unica_y_columnas(ruta):
    RegistroTranscripciones(ruta).registrar("a.wav", 3.5, 800.0, 20)
    RegistroTranscripciones(ruta).registrar("b.wav", 1.0, 200.0, 5)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert lineas[0] == "fecha,archivo,segundos_audio,milisegundos,caracteres"
    assert len(lineas) == 3 and lineas[1].split(",")[1:] == ["a.wav", "3.5", "800.0", "20"]


def test_resumen_suma_las_filas(ruta):
    registro = RegistroTranscripciones(ruta)
    registro.registrar("a.wav", 3.5, 800.0, 20)
    registro.registrar("b.wav", 1.5, 200.0, 5)
    assert registro.resumen() == {"transcripciones": 2, "segundos_audio": 5.0, "milisegundos": 1000.0}


def test_error_al_escribir(tmp_path):
    with pytest.raises(ErrorPersistencia):
        RegistroTranscripciones(tmp_path).registrar("a.wav", 1, 1, 1)  # la ruta es una carpeta


def test_csv_corrupto_al_leer(ruta):
    ruta.parent.mkdir(parents=True)
    ruta.write_text("fecha,archivo\nhoy,a.wav\n", encoding="utf-8")
    with pytest.raises(ErrorPersistencia):
        RegistroTranscripciones(ruta).resumen()
