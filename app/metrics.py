"""Métricas por proceso con ventana acotada de latencias."""

import math
import os
import threading
from collections import deque
from typing import Deque, Dict, Sequence

DEFAULT_MAX_SAMPLES = 1000


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    """Calcula un percentil por el método del rango más cercano.

    :param sorted_values: Valores ordenados de menor a mayor.
    :param fraction: Fracción entre 0 y 1 (por ejemplo, 0.95).
    :return: El percentil, o 0 si no hay valores.
    """
    if not sorted_values:
        return 0
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[rank - 1]


class Metrics:
    """Contadores de peticiones, errores, latencias y tokens de este proceso.

    :param slo_p95_ms: Meta de latencia p95 en milisegundos.
    :param max_samples: Tamaño máximo de la ventana de latencias.
    """

    def __init__(self, slo_p95_ms: int, max_samples: int = DEFAULT_MAX_SAMPLES):
        self._slo_p95_ms = slo_p95_ms
        self._latencies: Deque[float] = deque(maxlen=max_samples)
        self._requests = 0
        self._errors = 0
        self._tokens = {"input": 0, "output": 0}
        self._cost_usd = 0.0
        self._lock = threading.Lock()

    def record_request(self, latency_ms: float, error: bool = False) -> None:
        """Registra una petición terminada.

        :param latency_ms: Latencia en milisegundos.
        :param error: Verdadero si terminó con error del servidor.
        """
        with self._lock:
            self._requests += 1
            self._errors += 1 if error else 0
            self._latencies.append(latency_ms)

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Acumula los tokens de una corrida del agente.

        :param input_tokens: Tokens de entrada.
        :param output_tokens: Tokens de salida.
        """
        with self._lock:
            self._tokens["input"] += input_tokens
            self._tokens["output"] += output_tokens

    def record_cost(self, cost_usd: float) -> None:
        """Acumula el costo de una respuesta.

        :param cost_usd: Costo en USD.
        """
        with self._lock:
            self._cost_usd += cost_usd

    def snapshot(self) -> Dict:
        """Devuelve el cuerpo de ``GET /metrics``.

        :return: Diccionario con pid, peticiones, tasa de error, latencias,
            tokens, costo acumulado y estado del SLO.
        """
        with self._lock:
            ordered = sorted(self._latencies)
            requests = self._requests
            p50 = percentile(ordered, 0.50)
            p95 = percentile(ordered, 0.95)
            return {
                "pid": os.getpid(),
                "requests": requests,
                "error_rate": self._errors / requests if requests else 0,
                "latency_ms": {"p50": p50, "p95": p95},
                "tokens": dict(self._tokens),
                "cost_usd": self._cost_usd,
                "slo": {
                    "p95_ms_target": self._slo_p95_ms,
                    "met": p95 < self._slo_p95_ms,
                },
            }
