"""Identificador de petición y log JSON de una línea por evento."""

import json
import re
import sys
import threading
import uuid
from contextvars import ContextVar
from typing import Any, Optional, TextIO

from app.clock import Clock

REQUEST_ID_MAX_LENGTH = 128
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]+")
NO_REQUEST_ID = "-"

request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)


client_var: ContextVar[Optional[str]] = ContextVar("client", default=None)


def resolve_request_id(raw: Optional[str]) -> str:
    """Valida el id enviado por el cliente o genera uno nuevo.

    Un id con espacios, saltos de línea u otros caracteres, o demasiado largo,
    se descarta para evitar inyección en el log.

    :param raw: Valor del encabezado ``X-Request-ID`` o ``None``.
    :return: El id recibido si es válido; si no, un UUID nuevo.
    """
    if (
        raw is not None
        and len(raw) <= REQUEST_ID_MAX_LENGTH
        and REQUEST_ID_PATTERN.fullmatch(raw)
    ):
        return raw
    return str(uuid.uuid4())


# Emisor con una sola operación pública (``emit``); es su contrato.
# pylint: disable-next=too-few-public-methods
class JsonLogger:
    """Emisor de eventos JSON, uno por línea.

    :param service: Valor del campo ``service``.
    :param clock: Reloj inyectado para el campo ``ts``.
    :param stream: Flujo de salida; si es ``None`` se usa ``sys.stdout``
        leído en el momento de emitir.
    """

    def __init__(self, service: str, clock: Clock, stream: Optional[TextIO] = None):
        self._service = service
        self._clock = clock
        self._stream = stream
        self._lock = threading.Lock()

    def emit(self, event: str, **fields: Any) -> None:
        """Escribe una línea JSON con los campos comunes y los indicados.

        :param event: Nombre del evento.
        :param fields: Campos adicionales del evento.
        """
        stamp = self._clock.now().isoformat().replace("+00:00", "Z")
        record = {
            "ts": stamp,
            "service": self._service,
            "event": event,
            "request_id": request_id_var.get(),
        }
        client = client_var.get()
        if client is not None:
            record["client"] = client
        record.update(fields)
        line = json.dumps(record, ensure_ascii=False, default=str)
        stream = self._stream if self._stream is not None else sys.stdout
        with self._lock:
            stream.write(line + "\n")
            stream.flush()
