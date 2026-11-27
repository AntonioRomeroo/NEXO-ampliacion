from dotenv import load_dotenv

from dominio.herramientas import Calculadora, ConversorMoneda, BuscadorFAQ
from dominio.modelos import ModeloReglas
from dominio.transcriptor import TranscriptorLocal
from servicios.agente import Agente
from servicios.servicio_transcripcion import ServicioTranscripcion
from persistencia.registro_transcripciones import RegistroTranscripciones
from persistencia.repositorio_conversaciones import RepositorioConversaciones
from persistencia.registro_tokens import RegistroTokens
from persistencia.registro_uso import RegistroUso
from presentacion.chat_consola import ChatConsola

if __name__ == "__main__":
    load_dotenv()  # lee el archivo .env (clave y datos del LLM)
    herramientas = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]
    registro = RegistroUso("datos/uso.csv")
    agente = Agente(ModeloReglas(), herramientas, registro, RegistroTokens())
    transcripcion = ServicioTranscripcion(TranscriptorLocal(), RegistroTranscripciones())
    ChatConsola(agente, RepositorioConversaciones(), registro, transcripcion=transcripcion).iniciar()
