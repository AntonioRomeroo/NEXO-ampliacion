import csv
from datetime import datetime
from pathlib import Path

from dominio.excepciones import ErrorPersistencia


class RegistroTranscripciones:
    """Registro CSV de cada transcripción de audio (con el modelo local el coste es 0 €)."""

    COLUMNAS = ["fecha", "archivo", "segundos_audio", "milisegundos", "caracteres"]

    # Guarda la ruta del archivo CSV.
    def __init__(self, ruta="datos/transcripciones.csv"):
        self._ruta = Path(ruta)

    # Añade una fila al CSV (y la cabecera si el archivo está vacío).
    def registrar(self, archivo, segundos_audio, milisegundos, caracteres):
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            hay_cabecera = self._ruta.exists() and self._ruta.stat().st_size > 0
            with open(self._ruta, "a", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                if not hay_cabecera:
                    escritor.writerow(self.COLUMNAS)
                escritor.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    archivo,
                    round(segundos_audio, 2),
                    round(milisegundos, 2),
                    caracteres,
                ])
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo escribir el registro de transcripciones: {e}") from e

    # Lee el CSV y suma transcripciones, segundos de audio y tiempo de proceso.
    def resumen(self) -> dict:
        resumen = {"transcripciones": 0, "segundos_audio": 0.0, "milisegundos": 0.0}
        if not self._ruta.exists():
            return resumen
        try:
            with open(self._ruta, "r", newline="", encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    resumen["transcripciones"] += 1
                    resumen["segundos_audio"] += float(fila["segundos_audio"])
                    resumen["milisegundos"] += float(fila["milisegundos"])
        except (OSError, UnicodeDecodeError, csv.Error, KeyError, ValueError) as e:
            raise ErrorPersistencia(f"No se pudo leer el registro de transcripciones: {e}") from e
        return resumen
