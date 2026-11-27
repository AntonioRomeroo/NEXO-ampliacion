import struct
import sys
import wave
from types import SimpleNamespace

import pytest

from dominio.excepciones import ErrorAgente, ErrorTranscripcion
from dominio.transcriptor import (Transcriptor, TranscriptorLocal, _cargar_faster_whisper,
                                  _preparar_av, _WhisperLocal, leer_wav)


class WhisperFalso:
    """Imita a faster-whisper: devuelve trozos de texto y la duración del audio."""

    def __init__(self, textos=("hola", "que tal"), duracion=3.5, error=None):
        self.textos, self.duracion, self.error, self.llamadas = textos, duracion, error, []

    def transcribe(self, ruta, language=None):
        self.llamadas.append((ruta, language))
        if self.error:
            raise self.error
        return (SimpleNamespace(text=f" {t} ") for t in self.textos), SimpleNamespace(duration=self.duracion)


@pytest.fixture
def audio(tmp_path):
    ruta = tmp_path / "nota.wav"
    ruta.write_bytes(b"RIFF0000WAVE")
    return ruta


def _transcriptor(whisper=None, **opciones):
    whisper = whisper or WhisperFalso()
    cargas = []

    def cargador(nombre):
        cargas.append(nombre)
        return whisper

    return TranscriptorLocal(cargador=cargador, **opciones), whisper, cargas


def test_es_un_transcriptor():
    assert issubclass(TranscriptorLocal, Transcriptor)
    assert isinstance(TranscriptorLocal(), Transcriptor)


def test_la_clase_base_es_abstracta(audio):
    with pytest.raises(NotImplementedError):
        Transcriptor("base").transcribir(audio)


def test_transcribe_y_une_los_trozos(audio):
    transcriptor, whisper, _ = _transcriptor()
    assert transcriptor.transcribir(audio) == "hola que tal"
    assert whisper.llamadas == [(str(audio), "es")]


def test_guarda_el_uso_de_la_ultima_transcripcion(audio):
    transcriptor, _, _ = _transcriptor()
    assert transcriptor.ultimo_uso is None
    transcriptor.transcribir(audio)
    uso = transcriptor.ultimo_uso
    assert uso["archivo"] == "nota.wav" and uso["segundos_audio"] == 3.5
    assert uso["caracteres"] == len("hola que tal") and uso["milisegundos"] >= 0


def test_el_modelo_se_carga_una_sola_vez_y_solo_al_usarlo(audio):
    transcriptor, _, cargas = _transcriptor(modelo="small")
    assert cargas == []
    transcriptor.transcribir(audio)
    transcriptor.transcribir(audio)
    assert cargas == ["small"]


def test_el_modelo_sale_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("STT_MODELO", "tiny")
    assert TranscriptorLocal().modelo_whisper == "tiny"


def test_archivo_que_no_existe(tmp_path):
    transcriptor, _, cargas = _transcriptor()
    with pytest.raises(ErrorTranscripcion, match="No existe"):
        transcriptor.transcribir(tmp_path / "nada.wav")
    assert cargas == []  # ni siquiera se carga el modelo


def test_formato_no_soportado(tmp_path):
    texto = tmp_path / "notas.txt"
    texto.write_text("hola", encoding="utf-8")
    with pytest.raises(ErrorTranscripcion, match="Formato no soportado"):
        _transcriptor()[0].transcribir(texto)


def test_archivo_vacio(tmp_path):
    vacio = tmp_path / "vacio.mp3"
    vacio.write_bytes(b"")
    with pytest.raises(ErrorTranscripcion, match="vacío"):
        _transcriptor()[0].transcribir(vacio)


def test_audio_sin_voz(audio):
    transcriptor, _, _ = _transcriptor(WhisperFalso(textos=("  ",)))
    with pytest.raises(ErrorTranscripcion, match="No se ha entendido nada"):
        transcriptor.transcribir(audio)
    assert transcriptor.ultimo_uso is None


def test_un_fallo_del_modelo_se_convierte_en_error_transcripcion(audio):
    transcriptor, _, _ = _transcriptor(WhisperFalso(error=RuntimeError("audio roto")))
    with pytest.raises(ErrorTranscripcion, match="audio roto") as e:
        transcriptor.transcribir(audio)
    assert isinstance(e.value, ErrorAgente)


def test_si_falta_faster_whisper_el_mensaje_dice_como_instalarlo(monkeypatch):
    monkeypatch.setitem(sys.modules, "av", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # hace que "import faster_whisper" falle
    with pytest.raises(ErrorTranscripcion, match="requirements-audio.txt") as e:
        _cargar_faster_whisper("base")
    assert "Motivo:" in str(e.value)  # se enseña la causa real, no solo una frase genérica


# ---------- WAV y av bloqueado ----------

def _escribir_wav(ruta, muestras, tasa=16000, canales=1, ancho=2):
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(ancho)
        w.setframerate(tasa)
        w.writeframes(b"".join(struct.pack("<h", m) for m in muestras) if ancho == 2 else bytes(muestras))


def test_leer_wav_mono_16k(tmp_path):
    np = pytest.importorskip("numpy")
    _escribir_wav(tmp_path / "a.wav", [0, 16384, -16384, 32767])
    audio = leer_wav(tmp_path / "a.wav")
    assert audio.dtype == np.float32 and len(audio) == 4
    assert audio[1] == pytest.approx(0.5) and audio[2] == pytest.approx(-0.5)


def test_leer_wav_estereo_se_pasa_a_mono(tmp_path):
    pytest.importorskip("numpy")
    _escribir_wav(tmp_path / "e.wav", [16384, 0, 16384, 0], canales=2)  # 2 fotogramas: (0.5, 0)
    audio = leer_wav(tmp_path / "e.wav")
    assert len(audio) == 2 and audio[0] == pytest.approx(0.25)


def test_leer_wav_remuestrea_a_16k(tmp_path):
    pytest.importorskip("numpy")
    _escribir_wav(tmp_path / "b.wav", [0, 1000] * 4000, tasa=8000)  # 1 s a 8 kHz
    assert len(leer_wav(tmp_path / "b.wav")) == 16000


def test_leer_wav_rechaza_8_bits_vacios_y_falsos(tmp_path):
    pytest.importorskip("numpy")
    _escribir_wav(tmp_path / "ocho.wav", [128, 130, 120], ancho=1)
    with pytest.raises(ErrorTranscripcion, match="16 bits"):
        leer_wav(tmp_path / "ocho.wav")
    _escribir_wav(tmp_path / "vacio.wav", [])
    with pytest.raises(ErrorTranscripcion, match="no tiene sonido"):
        leer_wav(tmp_path / "vacio.wav")
    (tmp_path / "falso.wav").write_bytes(b"esto no es un wav")
    with pytest.raises(ErrorTranscripcion, match="no es válido"):
        leer_wav(tmp_path / "falso.wav")


def test_preparar_av_pone_un_av_falso_si_el_real_falla(monkeypatch):
    monkeypatch.setitem(sys.modules, "av", None)  # "import av" falla, como cuando Windows lo bloquea
    assert _preparar_av() is False
    import av  # ahora es el falso, así que faster-whisper podría importarse
    assert av is sys.modules["av"]


def test_whisper_local_con_av_pasa_la_ruta(tmp_path):
    modelo = WhisperFalso()
    assert _WhisperLocal(modelo, con_av=True).transcribe("x.mp3", language="es")
    assert modelo.llamadas == [("x.mp3", "es")]


def test_whisper_local_sin_av_lee_el_wav_y_pasa_el_sonido(tmp_path):
    np = pytest.importorskip("numpy")
    _escribir_wav(tmp_path / "v.wav", [0, 1000, -1000] * 100)
    modelo = WhisperFalso()
    _WhisperLocal(modelo, con_av=False).transcribe(str(tmp_path / "v.wav"), language="es")
    enviado = modelo.llamadas[0][0]
    assert isinstance(enviado, np.ndarray) and enviado.dtype == np.float32 and len(enviado) == 300


def test_whisper_local_sin_av_rechaza_otros_formatos():
    with pytest.raises(ErrorTranscripcion, match="solo se pueden transcribir archivos .wav"):
        _WhisperLocal(WhisperFalso(), con_av=False).transcribe("voz.mp3", language="es")
