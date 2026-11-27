import json
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from dominio.excepciones import ErrorAgente, ErrorLLM

NOMBRE_MODELO = "nexo"


# Saca el texto de un mensaje (puede ser un str o una lista de partes, según el frontend).
def _texto(contenido):
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return " ".join(p.get("text", "") for p in contenido if isinstance(p, dict))
    return ""


# Crea la app web: habla el formato de OpenAI para que cualquier frontend la entienda.
def crear_app(agente, transcripcion=None):
    app = FastAPI(title="NEXO")
    # CORS: sin esto el navegador bloquea las llamadas desde un index.html abierto en local.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # Error en el formato que los frontends de OpenAI saben mostrar.
    def error(codigo, mensaje):
        return JSONResponse(status_code=codigo, content={"error": {"message": mensaje}})

    # Lista de modelos (muchos frontends la piden al arrancar).
    @app.get("/v1/models")
    def modelos():
        return {"object": "list", "data": [{"id": NOMBRE_MODELO, "object": "model"}]}

    # Recibe la conversación del frontend y responde usando el Agente.
    @app.post("/v1/chat/completions")
    def chat(peticion: dict = Body(...)):
        mensajes = peticion.get("messages")
        if not isinstance(mensajes, list) or not mensajes:
            return error(400, "Falta la lista 'messages'")
        del_usuario = [_texto(m.get("content")) for m in mensajes if isinstance(m, dict) and m.get("role") == "user"]
        if not del_usuario or not del_usuario[-1].strip():
            return error(400, "No hay ningún mensaje del usuario")
        # El frontend manda TODO el historial, pero el Agente ya guarda el suyo:
        # solo usamos la última pregunta. Si es la única, es un chat nuevo.
        if len(del_usuario) == 1:
            agente.nueva_conversacion()
        try:
            texto = agente.procesar(del_usuario[-1])
        except ErrorLLM as e:
            return error(502, str(e))
        except ErrorAgente as e:
            return error(400, str(e))
        if peticion.get("stream"):
            return StreamingResponse(_trozos(texto), media_type="text/event-stream")
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": NOMBRE_MODELO,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": texto},
                         "finish_reason": "stop"}],
        }

    # Transcribe un audio (mismo formato que la API de OpenAI: multipart con el campo "file").
    @app.post("/v1/audio/transcriptions")
    def transcribir(file: UploadFile = File(...)):
        if transcripcion is None:
            return error(501, "La transcripción no está disponible")
        # Se guarda con su nombre original (sin carpetas) para que el registro y la extensión sean correctos.
        nombre = Path(file.filename or "audio").name
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / nombre
            ruta.write_bytes(file.file.read())
            try:
                texto = transcripcion.transcribir(ruta)
            except ErrorAgente as e:
                return error(400, str(e))
        return {"text": texto}

    return app


# Envía la respuesta ya calculada palabra a palabra, como un streaming (SSE) de OpenAI.
def _trozos(texto):
    id_ = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    def trozo(delta, fin=None):
        datos = {"id": id_, "object": "chat.completion.chunk", "created": int(time.time()),
                 "model": NOMBRE_MODELO, "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
        return f"data: {json.dumps(datos, ensure_ascii=False)}\n\n"

    yield trozo({"role": "assistant"})
    palabras = texto.split(" ")
    for i, palabra in enumerate(palabras):
        yield trozo({"content": palabra + (" " if i < len(palabras) - 1 else "")})
    yield trozo({}, "stop")
    yield "data: [DONE]\n\n"
