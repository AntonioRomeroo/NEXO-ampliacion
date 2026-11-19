import os
import time

import httpx

from dominio.excepciones import ErrorLLM, PeticionInvalida
from dominio.modelos import Modelo, Respuesta


class ModeloLLM(Modelo):
    """Modelo que habla con un LLM real por una API compatible con OpenAI (Ollama, OpenAI...)."""

    ROLES_API = {"usuario": "user", "asistente": "assistant", "herramienta": "user"}

    # Guarda la configuración; sin parámetros usa variables de entorno o los valores de Ollama.
    def __init__(self, modelo=None, base_url=None, api_key=None, max_tokens=150,
                 temperature=0.7, max_intentos=5, cliente=None, pausa=time.sleep):
        super().__init__("llm")
        self.modelo_llm = modelo or os.getenv("LLM_MODEL", "llama3")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self._api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_intentos = max_intentos
        self._cliente = cliente or httpx.Client(timeout=30)
        self._pausa = pausa
        self._ultimo_uso = None

    # Tokens de entrada y salida de la última respuesta (None si la API no los da).
    @property
    def ultimo_uso(self):
        return self._ultimo_uso

    # Comprueba la petición ANTES de enviarla; si algo falla, lanza PeticionInvalida.
    def validar(self, mensajes):
        if not mensajes:
            raise PeticionInvalida("No hay mensajes que enviar")
        if mensajes[-1]["role"] != "user":
            raise PeticionInvalida("El último mensaje debe ser del usuario")
        if self.max_tokens <= 0:
            raise PeticionInvalida("max_tokens debe ser mayor que 0")
        if not 0 <= self.temperature <= 2:
            raise PeticionInvalida("temperature debe estar entre 0 y 2")

    # Pasa los mensajes de NEXO (usuario/asistente/herramienta) al formato de la API.
    def _a_formato_api(self, conversacion):
        mensajes = []
        for m in conversacion.get_mensajes():
            texto = f"[Resultado de herramienta] {m.contenido}" if m.rol == "herramienta" else m.contenido
            mensajes.append({"role": self.ROLES_API[m.rol], "content": texto})
        return mensajes

    # Envía la conversación al LLM y devuelve su texto como Respuesta final.
    def responder(self, conversacion, herramientas) -> Respuesta:
        mensajes = self._a_formato_api(conversacion)
        self.validar(mensajes)
        datos = self._enviar({
            "model": self.modelo_llm,
            "messages": mensajes,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        })
        try:
            texto = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ErrorLLM("La respuesta del LLM no tiene el formato esperado") from e
        uso = datos.get("usage") or {}
        self._ultimo_uso = {
            "tokens_entrada": uso.get("prompt_tokens"),
            "tokens_salida": uso.get("completion_tokens"),
        }
        return Respuesta(texto=texto)

    # Hace la petición; reintenta con esperas crecientes solo si el error es 429 o 5xx.
    def _enviar(self, payload):
        cabeceras = {"Authorization": f"Bearer {self._api_key}"}
        for intento in range(1, self.max_intentos + 1):
            try:
                r = self._cliente.post(f"{self.base_url}/chat/completions", json=payload, headers=cabeceras)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                codigo = e.response.status_code
                if (codigo == 429 or codigo >= 500) and intento < self.max_intentos:
                    self._pausa(min(2 ** intento, 10))
                    continue
                raise ErrorLLM(f"El LLM respondió con error {codigo}") from e
            except httpx.TransportError as e:
                raise ErrorLLM(f"No se pudo conectar con el LLM en {self.base_url}") from e
            except ValueError as e:
                raise ErrorLLM("La respuesta del LLM no es JSON válido") from e
