import os

import uvicorn

from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.modelo_llm import ModeloLLM
from dominio.modelos import ModeloEco, ModeloReglas
from persistencia.registro_uso import RegistroUso
from presentacion.api_web import crear_app
from servicios.agente import Agente

MODELOS = {"reglas": ModeloReglas, "eco": ModeloEco, "llm": ModeloLLM}

# Arranca la API web de NEXO. Modelo: variable NEXO_MODELO (reglas por defecto).
if __name__ == "__main__":
    modelo = MODELOS[os.getenv("NEXO_MODELO", "reglas")]()
    herramientas = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]
    agente = Agente(modelo, herramientas, RegistroUso("datos/uso.csv"))
    uvicorn.run(crear_app(agente), host="127.0.0.1", port=8000)
