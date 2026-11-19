from dominio.excepciones import ErrorPersistencia
from dominio.modelos import Respuesta
from persistencia.registro_tokens import RegistroTokens
from servicios.agente import Agente
from tests.ayudantes import crear_agente, ejecutar_chat


class ModeloConTokens:
    nombre = "falso"
    ultimo_uso = {"tokens_entrada": 7, "tokens_salida": 40}

    def responder(self, conversacion, herramientas):
        return Respuesta(texto="vale")


def test_el_agente_anota_los_tokens_del_modelo(tmp_path):
    registro = RegistroTokens(tmp_path / "uso_llm.csv")
    agente = Agente(ModeloConTokens(), [], registro_tokens=registro)
    assert agente.procesar("¿qué tal?") == "vale"
    assert registro.resumen()["tokens_salida"] == 40
    assert "¿qué tal?" in (tmp_path / "uso_llm.csv").read_text(encoding="utf-8")


def test_un_modelo_sin_tokens_no_escribe_nada(tmp_path):
    registro = RegistroTokens(tmp_path / "uso_llm.csv")
    agente = crear_agente()  # ModeloReglas no informa de tokens
    agente._registro_tokens = registro
    agente.procesar("hola")
    assert not (tmp_path / "uso_llm.csv").exists()


def test_sin_registro_de_tokens_todo_sigue_igual():
    assert Agente(ModeloConTokens(), []).procesar("hola") == "vale"


class RegistroRoto:
    def registrar(self, *args):
        raise ErrorPersistencia("archivo bloqueado")


def test_si_falla_el_registro_de_tokens_la_respuesta_no_se_pierde():
    agente = Agente(ModeloConTokens(), [], registro_tokens=RegistroRoto())
    assert agente.procesar("hola") == "vale"
    assert "bloqueado" in agente.aviso


def test_si_falla_el_registro_de_herramientas_la_respuesta_no_se_pierde():
    agente = crear_agente(RegistroRoto())
    assert "4" in agente.procesar("2 + 2")
    assert "bloqueado" in agente.aviso


def test_el_aviso_se_borra_en_el_turno_siguiente():
    agente = crear_agente(RegistroRoto())
    agente.procesar("2 + 2")
    agente.procesar("hola")  # no usa herramientas: no hay nada que registrar
    assert agente.aviso is None


def test_el_chat_muestra_el_aviso_y_sigue_abierto():
    salida = ejecutar_chat(["2 + 2", "hola", "/salir"], crear_agente(RegistroRoto()))
    assert "NEXO > " in salida and "⚠ archivo bloqueado" in salida and "¡Hola!" in salida
