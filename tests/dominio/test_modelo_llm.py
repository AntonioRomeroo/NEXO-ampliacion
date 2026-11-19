import json

import httpx
import pytest

from dominio.excepciones import ErrorAgente, ErrorLLM, PeticionInvalida
from dominio.mensaje import Conversacion, Mensaje
from dominio.modelo_llm import ModeloLLM
from dominio.modelos import Modelo

OK = {"choices": [{"message": {"content": "Hola, soy un LLM"}}],
      "usage": {"prompt_tokens": 12, "completion_tokens": 5}}


def _conversacion(*mensajes):
    conversacion = Conversacion()
    for rol, contenido in mensajes:
        conversacion.agregar(Mensaje(rol, contenido))
    return conversacion


def _modelo(respuestas, **opciones):
    """ModeloLLM con una API falsa: devuelve las respuestas en orden y guarda las peticiones."""
    peticiones, cola = [], list(respuestas)

    def manejador(request):
        peticiones.append(request)
        resultado = cola.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        codigo, cuerpo = resultado
        return httpx.Response(codigo, json=cuerpo)

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    esperas = []
    modelo = ModeloLLM(base_url="http://falso/v1", cliente=cliente, pausa=esperas.append, **opciones)
    return modelo, peticiones, esperas


def test_es_un_modelo():
    modelo, _, _ = _modelo([])
    assert isinstance(modelo, Modelo) and modelo.nombre == "llm"


def test_devuelve_el_texto_y_guarda_el_uso():
    modelo, _, _ = _modelo([(200, OK)])
    respuesta = modelo.responder(_conversacion(("usuario", "hola")), [])
    assert respuesta.texto == "Hola, soy un LLM" and not respuesta.es_llamada_herramienta()
    assert modelo.ultimo_uso == {"tokens_entrada": 12, "tokens_salida": 5}


def test_traduce_los_roles_al_formato_de_la_api():
    modelo, peticiones, _ = _modelo([(200, OK)])
    modelo.responder(_conversacion(("usuario", "a"), ("asistente", "b"), ("usuario", "c")), [])
    cuerpo = json.loads(peticiones[0].content)
    assert [m["role"] for m in cuerpo["messages"]] == ["user", "assistant", "user"]
    assert peticiones[0].url.path == "/v1/chat/completions"


@pytest.mark.parametrize("opciones", [{"max_tokens": 0}, {"temperature": 3}, {"temperature": -1}])
def test_valida_antes_de_enviar(opciones):
    modelo, peticiones, _ = _modelo([(200, OK)], **opciones)
    with pytest.raises(PeticionInvalida):
        modelo.responder(_conversacion(("usuario", "hola")), [])
    assert peticiones == []


def test_conversacion_vacia_o_sin_pregunta_del_usuario():
    modelo, peticiones, _ = _modelo([(200, OK)])
    with pytest.raises(PeticionInvalida):
        modelo.responder(Conversacion(), [])
    with pytest.raises(PeticionInvalida):
        modelo.responder(_conversacion(("usuario", "hola"), ("asistente", "qué tal")), [])
    assert peticiones == []


def test_reintenta_con_429_y_luego_funciona():
    modelo, peticiones, esperas = _modelo([(429, {}), (503, {}), (200, OK)])
    assert modelo.responder(_conversacion(("usuario", "hola")), []).texto == "Hola, soy un LLM"
    assert len(peticiones) == 3 and esperas == [2, 4]


def test_se_rinde_tras_cinco_intentos():
    modelo, peticiones, _ = _modelo([(429, {})] * 5)
    with pytest.raises(ErrorLLM):
        modelo.responder(_conversacion(("usuario", "hola")), [])
    assert len(peticiones) == 5


@pytest.mark.parametrize("codigo", [400, 401, 404])
def test_no_reintenta_otros_errores(codigo):
    modelo, peticiones, _ = _modelo([(codigo, {})])
    with pytest.raises(ErrorLLM):
        modelo.responder(_conversacion(("usuario", "hola")), [])
    assert len(peticiones) == 1


def test_sin_conexion_da_un_error_claro():
    modelo, _, _ = _modelo([httpx.ConnectError("rechazada")])
    with pytest.raises(ErrorLLM, match="conectar"):
        modelo.responder(_conversacion(("usuario", "hola")), [])


def test_respuesta_con_formato_raro():
    modelo, _, _ = _modelo([(200, {"otra": "cosa"})])
    with pytest.raises(ErrorLLM, match="formato"):
        modelo.responder(_conversacion(("usuario", "hola")), [])


def test_los_errores_nuevos_son_errores_del_agente():
    assert issubclass(PeticionInvalida, ErrorAgente) and issubclass(ErrorLLM, ErrorAgente)
