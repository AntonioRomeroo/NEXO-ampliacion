import pytest

from dominio.excepciones import ErrorTranscripcion
from dominio.transcriptor import Transcriptor
from persistencia.registro_transcripciones import RegistroTranscripciones
from servicios.servicio_transcripcion import ServicioTranscripcion


class TranscriptorFalso(Transcriptor):
    def __init__(self, texto="dos mas dos"):
        super().__init__("falso")
        self.texto = texto

    def _transcribir(self, ruta):
        return self.texto, 2.0


@pytest.fixture
def audio(tmp_path):
    ruta = tmp_path / "voz.mp3"
    ruta.write_bytes(b"ID3")
    return ruta


def test_transcribe_y_anota(tmp_path, audio):
    registro = RegistroTranscripciones(tmp_path / "t.csv")
    servicio = ServicioTranscripcion(TranscriptorFalso(), registro)
    assert servicio.transcribir(audio) == "dos mas dos"
    assert servicio.aviso is None
    assert registro.resumen()["transcripciones"] == 1
    assert servicio.resumen()["segundos_audio"] == 2.0


def test_funciona_sin_registro(audio):
    servicio = ServicioTranscripcion(TranscriptorFalso())
    assert servicio.transcribir(audio) == "dos mas dos"
    assert servicio.resumen() is None


def test_si_falla_el_csv_deja_aviso_y_no_pierde_el_texto(tmp_path, audio):
    servicio = ServicioTranscripcion(TranscriptorFalso(), RegistroTranscripciones(tmp_path))  # ruta = carpeta
    assert servicio.transcribir(audio) == "dos mas dos"
    assert "No se pudo escribir" in servicio.aviso


def test_el_aviso_se_borra_en_la_siguiente_transcripcion(tmp_path, audio):
    servicio = ServicioTranscripcion(TranscriptorFalso(), RegistroTranscripciones(tmp_path))
    servicio.transcribir(audio)
    servicio._registro = None
    servicio.transcribir(audio)
    assert servicio.aviso is None


def test_los_errores_del_transcriptor_suben(tmp_path):
    servicio = ServicioTranscripcion(TranscriptorFalso())
    with pytest.raises(ErrorTranscripcion):
        servicio.transcribir(tmp_path / "no_existe.wav")
