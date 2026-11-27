from dominio.excepciones import ErrorPersistencia


class ServicioTranscripcion:
    """Pasa un audio a texto y anota la transcripción. Lo usan el chat y la API web."""

    # Recibe el transcriptor y, si se quiere, el registro CSV.
    def __init__(self, transcriptor, registro=None):
        self._transcriptor = transcriptor
        self._registro = registro
        self._aviso = None

    # Aviso de la última transcripción (por ejemplo, que no se pudo escribir el CSV); None si todo fue bien.
    @property
    def aviso(self):
        return self._aviso

    # Transcribe el archivo y lo anota; si el CSV falla, deja un aviso y el texto no se pierde.
    def transcribir(self, ruta) -> str:
        self._aviso = None
        texto = self._transcriptor.transcribir(ruta)
        if self._registro is not None:
            uso = self._transcriptor.ultimo_uso
            try:
                self._registro.registrar(uso["archivo"], uso["segundos_audio"],
                                         uso["milisegundos"], uso["caracteres"])
            except ErrorPersistencia as e:
                self._aviso = str(e)
        return texto

    # Resumen del registro (None si no hay registro).
    def resumen(self):
        return self._registro.resumen() if self._registro is not None else None
