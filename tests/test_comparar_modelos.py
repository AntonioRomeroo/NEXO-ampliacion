import csv

from comparar_modelos import PREGUNTAS, comparar, guardar_csv, resumir
from dominio.excepciones import ErrorLLM
from dominio.modelos import ModeloEco, ModeloReglas, Respuesta
from persistencia.registro_tokens import RegistroTokens


class LLMFalso:
    nombre = "llm"
    ultimo_uso = None

    def responder(self, conversacion, herramientas):
        self.ultimo_uso = {"tokens_entrada": 5, "tokens_salida": 20}
        return Respuesta(texto="respuesta del llm")


class LLMRoto:
    nombre = "llm"
    ultimo_uso = None

    def responder(self, conversacion, herramientas):
        raise ErrorLLM("sin conexión")


def test_hay_diez_preguntas_distintas():
    assert len(PREGUNTAS) == 10 and len(set(PREGUNTAS)) == 10


def test_guarda_una_respuesta_por_pregunta_y_modelo():
    r = comparar(PREGUNTAS, {"reglas": ModeloReglas(), "llm": LLMFalso()})
    for datos in r.values():
        assert len(datos["respuestas"]) == len(datos["tiempos"]) == len(datos["tokens"]) == 10
    assert "12 * 7 = 84" in r["reglas"]["respuestas"][0]
    assert sum(r["llm"]["tokens"]) == 200 and sum(r["reglas"]["tokens"]) == 0


def test_un_error_del_modelo_se_cuenta_y_no_para_la_comparacion():
    r = comparar(PREGUNTAS, {"llm": LLMRoto(), "eco": ModeloEco()})
    assert r["llm"]["errores"] == 10 and r["llm"]["respuestas"][0].startswith("ERROR")
    assert r["eco"]["errores"] == 0 and len(r["eco"]["respuestas"]) == 10


def test_cada_pregunta_empieza_sin_historial():
    r = comparar(["hola", "hola"], {"reglas": ModeloReglas()})
    assert r["reglas"]["respuestas"][0] == r["reglas"]["respuestas"][1]


def test_resumen_y_csv(tmp_path):
    registro = RegistroTokens(tmp_path / "uso_llm.csv")
    r = comparar(PREGUNTAS, {"reglas": ModeloReglas(), "llm": LLMFalso()}, registro)
    resumen = resumir(r, registro)
    assert resumen["llm"]["tokens_salida"] == 200
    assert resumen["llm"]["coste"] == registro.calcular_coste(200)
    assert registro.resumen()["peticiones"] == 10  # solo el LLM anota tokens
    ruta = tmp_path / "comparacion.csv"
    guardar_csv(ruta, PREGUNTAS, r)
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        filas = list(csv.reader(f, delimiter=";"))
    assert len(filas) == 11 and filas[0][0] == "pregunta"
