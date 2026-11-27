from dominio.transcriptor import Transcriptor
from persistencia.registro_transcripciones import RegistroTranscripciones
from persistencia.registro_uso import RegistroUso
from servicios.servicio_transcripcion import ServicioTranscripcion
from tests.ayudantes import crear_agente, ejecutar_chat


class TranscriptorFalso(Transcriptor):
    def __init__(self, texto="cuánto tarda el envío?"):
        super().__init__("falso")
        self.texto = texto

    def _transcribir(self, ruta):
        return self.texto, 4.0


def _servicio(tmp_path, texto="cuánto tarda el envío?"):
    return ServicioTranscripcion(TranscriptorFalso(texto), RegistroTranscripciones(tmp_path / "t.csv"))


def _audio(tmp_path, nombre="pregunta.wav"):
    ruta = tmp_path / nombre
    ruta.write_bytes(b"RIFF")
    return ruta


def test_transcribir_envia_el_texto_a_nexo(tmp_path):
    texto = ejecutar_chat([f"/transcribir {_audio(tmp_path)}"], crear_agente(),
                          transcripcion=_servicio(tmp_path))
    assert "🎙 Transcripción: cuánto tarda el envío?" in texto
    assert "Según nuestra información: Los envíos tardan 24-48 h" in texto


def test_acepta_la_ruta_entre_comillas(tmp_path):
    ruta = _audio(tmp_path, "mi pregunta.wav")
    texto = ejecutar_chat([f'/transcribir "{ruta}"'], crear_agente(), transcripcion=_servicio(tmp_path))
    assert "🎙 Transcripción:" in texto and "⚠" not in texto


def test_sin_servicio_avisa(tmp_path):
    texto = ejecutar_chat([f"/transcribir {_audio(tmp_path)}"], crear_agente())
    assert "⚠ La transcripción no está disponible." in texto


def test_sin_argumento_explica_el_uso(tmp_path):
    texto = ejecutar_chat(["/transcribir"], crear_agente(), transcripcion=_servicio(tmp_path))
    assert "Uso: /transcribir <archivo de audio>" in texto


def test_un_archivo_malo_no_cierra_el_chat(tmp_path):
    texto = ejecutar_chat(["/transcribir no_existe.wav", "hola"], crear_agente(),
                          transcripcion=_servicio(tmp_path))
    assert "⚠ No existe el archivo de audio" in texto
    assert "NEXO > ¡Hola!" in texto


def test_el_aviso_del_csv_se_muestra_pero_la_respuesta_llega(tmp_path):
    servicio = ServicioTranscripcion(TranscriptorFalso(), RegistroTranscripciones(tmp_path))  # ruta = carpeta
    texto = ejecutar_chat([f"/transcribir {_audio(tmp_path)}"], crear_agente(), transcripcion=servicio)
    assert "⚠ No se pudo escribir el registro de transcripciones" in texto
    assert "Según nuestra información" in texto


def test_stats_muestra_las_transcripciones(tmp_path):
    texto = ejecutar_chat([f"/transcribir {_audio(tmp_path)}", "/stats"], crear_agente(),
                          registro=RegistroUso(tmp_path / "uso.csv"), transcripcion=_servicio(tmp_path))
    assert "🎙 Transcripciones: 1 (4.0 s de audio)" in texto
