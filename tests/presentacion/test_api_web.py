import json

import pytest
from fastapi.testclient import TestClient

from presentacion.api_web import crear_app
from tests.ayudantes import crear_agente


@pytest.fixture
def cliente():
    return TestClient(crear_app(crear_agente()))


def _pedir(cliente, *textos, **extra):
    mensajes = [{"role": "user" if i % 2 == 0 else "assistant", "content": t} for i, t in enumerate(textos)]
    return cliente.post("/v1/chat/completions", json={"messages": mensajes, **extra})


def test_responde_en_formato_openai(cliente):
    r = _pedir(cliente, "3 * 4")
    cuerpo = r.json()
    assert r.status_code == 200 and cuerpo["object"] == "chat.completion"
    assert "12" in cuerpo["choices"][0]["message"]["content"]
    assert cuerpo["choices"][0]["message"]["role"] == "assistant"


def test_acepta_contenido_en_lista_de_partes(cliente):
    r = cliente.post("/v1/chat/completions",
                     json={"messages": [{"role": "user", "content": [{"type": "text", "text": "3 * 4"}]}]})
    assert "12" in r.json()["choices"][0]["message"]["content"]


def test_streaming_termina_con_done(cliente):
    r = _pedir(cliente, "hola", stream=True)
    lineas = [l for l in r.text.split("\n\n") if l]
    assert r.headers["content-type"].startswith("text/event-stream")
    assert lineas[-1] == "data: [DONE]"
    texto = "".join(json.loads(l[6:])["choices"][0]["delta"].get("content", "") for l in lineas[:-1])
    assert texto.startswith("¡Hola!")


def test_primer_mensaje_empieza_chat_nuevo_y_los_siguientes_siguen(cliente):
    agente = crear_agente()
    cliente = TestClient(crear_app(agente))
    _pedir(cliente, "hola")
    id_primero = agente.conversacion.id
    _pedir(cliente, "hola", "¡Hola!", "3 * 4")  # mismo chat: no se reinicia
    assert agente.conversacion.id == id_primero
    _pedir(cliente, "hola")                      # un solo mensaje: chat nuevo
    assert agente.conversacion.id != id_primero


@pytest.mark.parametrize("cuerpo", [{}, {"messages": []}, {"messages": [{"role": "user", "content": "  "}]},
                                    {"messages": [{"role": "assistant", "content": "hola"}]}])
def test_peticiones_malas_dan_400_con_mensaje(cliente, cuerpo):
    r = cliente.post("/v1/chat/completions", json=cuerpo)
    assert r.status_code == 400 and r.json()["error"]["message"]


def test_cors_permite_el_frontend(cliente):
    r = cliente.options("/v1/chat/completions", headers={
        "Origin": "null", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"


def test_lista_de_modelos(cliente):
    assert cliente.get("/v1/models").json()["data"][0]["id"] == "nexo"
