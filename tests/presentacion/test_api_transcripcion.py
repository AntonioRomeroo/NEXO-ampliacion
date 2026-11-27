import pytest
from fastapi.testclient import TestClient

from dominio.transcriptor import Transcriptor
from persistencia.registro_transcripciones import RegistroTranscripciones
from presentacion.api_web import crear_app
from servicios.servicio_transcripcion import ServicioTranscripcion
from tests.ayudantes import crear_agente


class TranscriptorFalso(Transcriptor):
    def __init__(self):
        super().__init__("falso")
        self.rutas = []

    def _transcribir(self, ruta):
        self.rutas.append(ruta)
        return "hola desde el audio", 2.0


@pytest.fixture
def montaje(tmp_path):
    transcriptor = TranscriptorFalso()
    registro = RegistroTranscripciones(tmp_path / "t.csv")
    cliente = TestClient(crear_app(crear_agente(), ServicioTranscripcion(transcriptor, registro)))
    return cliente, transcriptor, registro


def test_transcribe_en_formato_openai(montaje):
    cliente, _, registro = montaje
    r = cliente.post("/v1/audio/transcriptions", files={"file": ("voz.wav", b"RIFF0000", "audio/wav")})
    assert r.status_code == 200 and r.json() == {"text": "hola desde el audio"}
    assert registro.resumen()["transcripciones"] == 1


def test_conserva_el_nombre_pero_no_las_carpetas(montaje):
    cliente, transcriptor, _ = montaje
    cliente.post("/v1/audio/transcriptions", files={"file": ("../../x/voz.mp3", b"ID3", "audio/mpeg")})
    assert transcriptor.rutas[0].name == "voz.mp3"
    assert not transcriptor.rutas[0].exists()  # el archivo temporal se borra


def test_formato_malo_da_400_con_mensaje(montaje):
    cliente, _, _ = montaje
    r = cliente.post("/v1/audio/transcriptions", files={"file": ("notas.txt", b"hola", "text/plain")})
    assert r.status_code == 400 and "Formato no soportado" in r.json()["error"]["message"]


def test_archivo_vacio_da_400(montaje):
    cliente, _, _ = montaje
    r = cliente.post("/v1/audio/transcriptions", files={"file": ("vacio.wav", b"", "audio/wav")})
    assert r.status_code == 400


def test_sin_archivo_da_error_de_validacion(montaje):
    assert montaje[0].post("/v1/audio/transcriptions").status_code == 422


def test_sin_servicio_da_501():
    cliente = TestClient(crear_app(crear_agente()))
    r = cliente.post("/v1/audio/transcriptions", files={"file": ("voz.wav", b"RIFF", "audio/wav")})
    assert r.status_code == 501 and r.json()["error"]["message"]
