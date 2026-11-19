import csv
from datetime import datetime
from pathlib import Path

from dominio.excepciones import ErrorPersistencia


class RegistroTokens:
    """Registro CSV de los tokens y el coste de cada respuesta del LLM."""

    COLUMNAS = ["fecha", "pregunta", "tokens_entrada", "tokens_salida", "coste"]
    # Precio de ejemplo de la guía: euros por cada 1000 tokens de salida. Cámbialo si el profesor da otro.
    PRECIO_POR_1000 = 0.008

    # Guarda la ruta del CSV y el precio por cada 1000 tokens de salida.
    def __init__(self, ruta="datos/uso_llm.csv", precio_por_1000=PRECIO_POR_1000):
        self._ruta = Path(ruta)
        self._precio = precio_por_1000

    # Calcula el coste en euros a partir de los tokens de salida.
    def calcular_coste(self, tokens_salida):
        return (tokens_salida or 0) * self._precio / 1000

    # Añade una fila al CSV (y la cabecera si el archivo está vacío).
    def registrar(self, pregunta, tokens_entrada, tokens_salida):
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            hay_cabecera = self._ruta.exists() and self._ruta.stat().st_size > 0
            with open(self._ruta, "a", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                if not hay_cabecera:
                    escritor.writerow(self.COLUMNAS)
                escritor.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    pregunta,
                    tokens_entrada or 0,
                    tokens_salida or 0,
                    f"{self.calcular_coste(tokens_salida):.6f}",
                ])
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo escribir el registro de tokens: {e}") from e

    # Lee el CSV y suma peticiones, tokens y coste.
    def resumen(self) -> dict:
        resumen = {"peticiones": 0, "tokens_entrada": 0, "tokens_salida": 0, "coste": 0.0}
        if not self._ruta.exists():
            return resumen
        try:
            with open(self._ruta, "r", newline="", encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    resumen["peticiones"] += 1
                    resumen["tokens_entrada"] += int(fila["tokens_entrada"])
                    resumen["tokens_salida"] += int(fila["tokens_salida"])
                    resumen["coste"] += float(fila["coste"])
        except (OSError, UnicodeDecodeError, csv.Error, KeyError, ValueError) as e:
            raise ErrorPersistencia(f"No se pudo leer el registro de tokens: {e}") from e
        return resumen
