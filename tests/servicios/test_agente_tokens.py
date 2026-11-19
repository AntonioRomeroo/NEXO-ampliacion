from dominio.modelos import Respuesta
from persistencia.registro_tokens import RegistroTokens
from servicios.agente import Agente
from tests.ayudantes import crear_agente


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
