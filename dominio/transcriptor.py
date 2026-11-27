import os
import sys
import time
import types
import wave
from pathlib import Path

from dominio.excepciones import ErrorTranscripcion


# Lee un .wav de 16 bits con la librería estándar y lo devuelve en mono, 16 kHz y float32 (lo que espera Whisper).
def leer_wav(ruta, tasa_objetivo=16000):
    import numpy as np  # solo hace falta en este camino; ya viene con ctranslate2
    try:
        with wave.open(str(ruta), "rb") as wav:
            canales, ancho, tasa = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            datos = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as e:
        raise ErrorTranscripcion(f"El archivo WAV no es válido: {e}") from e
    if ancho != 2:
        raise ErrorTranscripcion(f"Solo se pueden leer WAV de 16 bits (este es de {ancho * 8} bits)")
    audio = np.frombuffer(datos, dtype="<i2").astype(np.float32) / 32768.0
    if canales > 1:  # varios canales -> media = mono
        audio = audio[: len(audio) // canales * canales].reshape(-1, canales).mean(axis=1)
    if audio.size == 0:
        raise ErrorTranscripcion("El audio WAV no tiene sonido")
    if tasa != tasa_objetivo:  # remuestreo sencillo por interpolación
        destino = max(1, round(len(audio) * tasa_objetivo / tasa))
        audio = np.interp(np.linspace(0, len(audio) - 1, destino), np.arange(len(audio)), audio)
    return audio.astype(np.float32)


# Devuelve True si la librería av funciona. Si no (p. ej. Windows la bloquea con el "Control de aplicaciones"),
# pone un av falso para que faster-whisper se pueda importar; entonces solo se leen archivos .wav.
def _preparar_av():
    try:
        import av  # noqa: F401
        return True
    except ImportError:
        sys.modules["av"] = types.ModuleType("av")
        return False


class _WhisperLocal:
    """Envuelve a WhisperModel: con av le pasa la ruta; sin av, lee el .wav por su cuenta y le pasa el sonido."""

    # Guarda el modelo y si av funciona.
    def __init__(self, modelo, con_av):
        self._modelo = modelo
        self._con_av = con_av

    # Misma forma que WhisperModel.transcribe(): devuelve (trozos, info).
    def transcribe(self, ruta, language=None):
        if self._con_av:
            return self._modelo.transcribe(ruta, language=language)
        if not str(ruta).lower().endswith(".wav"):
            raise ErrorTranscripcion(
                "En este ordenador solo se pueden transcribir archivos .wav (Windows bloquea la librería 'av'). "
                "La página web convierte el audio a .wav sola; en la consola usa un .wav."
            )
        return self._modelo.transcribe(leer_wav(ruta), language=language)


# Carga el modelo Whisper en local. faster_whisper se importa aquí para que NEXO funcione sin instalarlo.
def _cargar_faster_whisper(nombre):
    con_av = _preparar_av()
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ErrorTranscripcion(
            f"No se pudo cargar faster-whisper. Motivo: {e}. Si no lo has instalado, usa estos dos comandos: "
            "pip install -r requirements-audio.txt  y después  pip install --no-deps faster-whisper"
        ) from e
    return _WhisperLocal(WhisperModel(nombre, device="cpu", compute_type="int8"), con_av)


class Transcriptor:
    """Clase base: pasa un archivo de audio a texto. Cada hija decide cómo transcribir."""

    EXTENSIONES = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm")

    # Guarda el nombre del transcriptor.
    def __init__(self, nombre):
        self.nombre = nombre
        self._ultimo_uso = None

    # Datos de la última transcripción: archivo, segundos de audio, milisegundos y caracteres.
    @property
    def ultimo_uso(self):
        return self._ultimo_uso

    # Comprueba el archivo ANTES de transcribir; si algo falla, lanza ErrorTranscripcion.
    def validar(self, ruta):
        if not ruta.is_file():
            raise ErrorTranscripcion(f"No existe el archivo de audio: {ruta}")
        if ruta.suffix.lower() not in self.EXTENSIONES:
            raise ErrorTranscripcion(
                f"Formato no soportado: {ruta.suffix or '(sin extensión)'}. "
                f"Usa uno de: {', '.join(self.EXTENSIONES)}"
            )
        if ruta.stat().st_size == 0:
            raise ErrorTranscripcion(f"El archivo de audio está vacío: {ruta.name}")

    # Valida, transcribe, mide el tiempo y devuelve el texto.
    def transcribir(self, ruta) -> str:
        ruta = Path(ruta)
        self.validar(ruta)
        inicio = time.perf_counter()
        texto, segundos_audio = self._transcribir(ruta)
        texto = texto.strip()
        if not texto:
            raise ErrorTranscripcion(f"No se ha entendido nada en el audio: {ruta.name}")
        self._ultimo_uso = {
            "archivo": ruta.name,
            "segundos_audio": segundos_audio,
            "milisegundos": (time.perf_counter() - inicio) * 1000,
            "caracteres": len(texto),
        }
        return texto

    # Método abstracto: devuelve (texto, segundos de audio).
    def _transcribir(self, ruta):
        raise NotImplementedError("Cada transcriptor debe implementar _transcribir()")


class TranscriptorLocal(Transcriptor):
    """Transcribe en tu ordenador con faster-whisper: sin clave, sin internet (tras la primera descarga)."""

    # Guarda la configuración; el modelo no se carga hasta la primera transcripción.
    def __init__(self, modelo=None, idioma="es", cargador=None):
        super().__init__("local")
        self.modelo_whisper = modelo or os.getenv("STT_MODELO", "base")
        self.idioma = idioma
        self._cargador = cargador or _cargar_faster_whisper
        self._modelo = None

    # Carga el modelo solo la primera vez (la descarga puede tardar).
    def _modelo_cargado(self):
        if self._modelo is None:
            self._modelo = self._cargador(self.modelo_whisper)
        return self._modelo

    # Transcribe con Whisper y une los trozos en un solo texto.
    def _transcribir(self, ruta):
        modelo = self._modelo_cargado()
        try:
            trozos, info = modelo.transcribe(str(ruta), language=self.idioma)
            texto = " ".join(t.text.strip() for t in trozos)
        except ErrorTranscripcion:
            raise
        except Exception as e:  # un audio roto no debe cerrar el chat
            raise ErrorTranscripcion(f"No se pudo transcribir {ruta.name}: {e}") from e
        return texto, float(info.duration)
