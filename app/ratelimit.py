"""Límite de peticiones por cliente con ventana deslizante y reloj inyectado.

El estado vive en la memoria de cada proceso (ADR 0010). Solo se cuentan
clientes ya autenticados; los intentos con clave inválida NO tienen límite por
origen, decisión aceptada y documentada en ``auth.py``.
"""

import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict

from app.clock import Clock

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class Decision:
    """Resultado de una consulta al limitador.

    :param allowed: Verdadero si la petición puede atenderse.
    :param retry_after: Segundos enteros que faltan; 0 si se permite y al
        menos 1 si se niega.
    """

    allowed: bool
    retry_after: int = 0


# Limitador con una sola operación pública (``check``); es su contrato.
# pylint: disable-next=too-few-public-methods
class RateLimiter:
    """Cuenta peticiones por cliente en los últimos 60 segundos.

    :param limit: Peticiones permitidas por ventana.
    :param clock: Reloj inyectado.
    """

    def __init__(self, limit: int, clock: Clock):
        self._limit = limit
        self._clock = clock
        self._hits: Dict[str, Deque[datetime]] = {}
        self._lock = threading.Lock()

    def check(self, client: str) -> Decision:
        """Registra la petición del cliente si cabe en la ventana.

        Las peticiones negadas no se registran.

        :param client: Nombre del cliente autenticado.
        :return: La decisión con los segundos de espera cuando se niega.
        """
        now = self._clock.now()
        with self._lock:
            hits = self._hits.setdefault(client, deque())
            while hits and (now - hits[0]).total_seconds() >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= self._limit:
                age = (now - hits[0]).total_seconds()
                wait = math.ceil(WINDOW_SECONDS - age)
                return Decision(False, max(1, wait))
            hits.append(now)
            return Decision(True)
