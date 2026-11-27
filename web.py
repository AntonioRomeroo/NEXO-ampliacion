import os

import uvicorn
from dotenv import load_dotenv

from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.modelo_llm import ModeloLLM
from dominio.modelos import ModeloEco, ModeloReglas
from dominio.transcriptor import TranscriptorLocal
from persistencia.registro_transcripciones import RegistroTranscripciones
from persistencia.registro_tokens import RegistroTokens
from persistencia.registro_uso import RegistroUso
from presentacion.api_web import crear_app
from servicios.agente import Agente
from servicios.servicio_transcripcion import ServicioTranscripcion

MODELOS = {"reglas": ModeloReglas, "eco": ModeloEco, "llm": ModeloLLM}

# Arranca la API web de NEXO. Modelo: variable NEXO_MODELO (reglas por defecto).
if __name__ == "__main__":
    load_dotenv()  # lee el archivo .env (clave y datos del LLM)
    modelo = MODELOS[os.getenv("NEXO_MODELO", "reglas")]()
    herramientas = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]
    agente = Agente(modelo, herramientas, RegistroUso("datos/uso.csv"), RegistroTokens())
    transcripcion = ServicioTranscripcion(TranscriptorLocal(), RegistroTranscripciones())
    uvicorn.run(crear_app(agente, transcripcion), host="127.0.0.1", port=8000)
