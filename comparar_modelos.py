import csv
import time
from pathlib import Path

from dotenv import load_dotenv

from dominio.excepciones import ErrorAgente
from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.modelo_llm import ModeloLLM
from dominio.modelos import ModeloReglas
from persistencia.registro_tokens import RegistroTokens
from servicios.agente import Agente

PREGUNTAS = [
    "12 * 7",
    "cuánto son 250 USD en euros",
    "¿cuánto tardan los envíos a Canarias?",
    "¿qué horario tenéis?",
    "¿puedo pagar con Bizum?",
    "hola",
    "explícame qué es una lista en Python en dos frases",
    "¿cuál es la capital de Francia?",
    "dame una idea para el nombre de una tienda de tecnología",
    "multiplica 15 por 4 y luego réstale 10",
]


# Hace las mismas preguntas a cada modelo y guarda respuestas, tiempos, tokens y errores en listas.
def comparar(preguntas, modelos, registro_tokens=None):
    resultados = {}
    for nombre, modelo in modelos.items():
        herramientas = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]
        agente = Agente(modelo, herramientas, registro_tokens=registro_tokens)
        datos = {"respuestas": [], "tiempos": [], "tokens": [], "errores": 0}
        for pregunta in preguntas:
            agente.nueva_conversacion()  # cada pregunta empieza de cero
            inicio = time.perf_counter()
            fallo = False
            try:
                texto = agente.procesar(pregunta)
            except ErrorAgente as e:
                texto, fallo = f"ERROR: {e}", True
                datos["errores"] += 1
            datos["tiempos"].append(time.perf_counter() - inicio)
            uso = None if fallo else getattr(modelo, "ultimo_uso", None)
            datos["tokens"].append((uso or {}).get("tokens_salida") or 0)
            datos["respuestas"].append(texto)
        resultados[nombre] = datos
    return resultados


# Guarda la comparación en un CSV que Excel abre con doble clic (UTF-8 con marca y ";").
def guardar_csv(ruta, preguntas, resultados):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nombres = list(resultados)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(["pregunta"] + [f"{campo}_{n}" for n in nombres
                                          for campo in ("respuesta", "segundos", "tokens_salida")])
        for i, pregunta in enumerate(preguntas):
            fila = [pregunta]
            for n in nombres:
                d = resultados[n]
                fila += [d["respuestas"][i], f"{d['tiempos'][i]:.3f}", d["tokens"][i]]
            escritor.writerow(fila)


# Calcula el resumen de cada modelo: tiempo medio, tokens, coste y errores.
def resumir(resultados, registro_tokens):
    resumen = {}
    for nombre, d in resultados.items():
        tokens = sum(d["tokens"])
        resumen[nombre] = {
            "segundos_medios": sum(d["tiempos"]) / len(d["tiempos"]),
            "tokens_salida": tokens,
            "coste": registro_tokens.calcular_coste(tokens),
            "errores": d["errores"],
        }
    return resumen


# Enseña las respuestas lado a lado y el resumen por pantalla.
def mostrar(preguntas, resultados, resumen):
    for i, pregunta in enumerate(preguntas):
        print(f"\n{i + 1}. {pregunta}")
        for nombre, d in resultados.items():
            corta = d["respuestas"][i].replace("\n", " ")
            print(f"   [{nombre}] {corta[:90]}{'...' if len(corta) > 90 else ''}")
    print("\n--- Resumen ---")
    for nombre, r in resumen.items():
        print(f"{nombre}: {r['segundos_medios']:.2f} s de media, {r['tokens_salida']} tokens de salida, "
              f"{r['coste']:.6f} €, {r['errores']} errores")


if __name__ == "__main__":
    load_dotenv()
    registro = RegistroTokens()
    resultados = comparar(PREGUNTAS, {"reglas": ModeloReglas(), "llm": ModeloLLM()}, registro)
    guardar_csv("datos/comparacion.csv", PREGUNTAS, resultados)
    mostrar(PREGUNTAS, resultados, resumir(resultados, registro))
    print("\nGuardado en datos/comparacion.csv")
