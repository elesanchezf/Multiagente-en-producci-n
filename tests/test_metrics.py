"""Pruebas unitarias de las metricas por proceso.

Supuestos de interfaz: ``Metrics(slo_p95_ms, max_samples=1000)`` con
``record_request(latency_ms, error=False)``, ``record_tokens(input_tokens,
output_tokens)`` y ``snapshot()`` que devuelve el cuerpo de ``/metrics``.
"""

from app.metrics import Metrics


def _filled(latencies, slo_p95_ms=2000, **kwargs):
    metrics = Metrics(slo_p95_ms=slo_p95_ms, **kwargs)
    for latency in latencies:
        metrics.record_request(latency)
    return metrics


def test_percentiles_work_with_one_sample_and_with_many():
    """Los percentiles p50 y p95 se calculan con una muestra y con varias."""
    single = _filled([120]).snapshot()
    assert single["latency_ms"] == {"p50": 120, "p95": 120}
    snapshot = _filled(range(10, 110, 10)).snapshot()
    assert 50 <= snapshot["latency_ms"]["p50"] <= 60
    assert snapshot["latency_ms"]["p95"] >= 95


def test_no_requests_gives_zeros_without_dividing_by_zero():
    """Sin peticiones las metricas valen cero y no hay division entre cero."""
    snapshot = Metrics(slo_p95_ms=2000).snapshot()
    assert snapshot["requests"] == 0
    assert snapshot["error_rate"] == 0
    assert snapshot["latency_ms"] == {"p50": 0, "p95": 0}


def test_error_rate_and_tokens_are_accumulated():
    """La tasa de error y los tokens de entrada y salida se acumulan."""
    metrics = _filled([10, 10, 10])
    metrics.record_request(10, error=True)
    metrics.record_tokens(5, 2)
    metrics.record_tokens(4, 1)
    snapshot = metrics.snapshot()
    assert snapshot["requests"] == 4
    assert snapshot["error_rate"] == 0.25
    assert snapshot["tokens"] == {"input": 9, "output": 3}


def test_only_a_bounded_window_of_latencies_is_kept():
    """Solo se conserva una ventana acotada de latencias, pero se cuentan todas."""
    metrics = _filled([5000, 1, 1, 1], max_samples=3)
    snapshot = metrics.snapshot()
    assert snapshot["requests"] == 4
    assert snapshot["latency_ms"]["p95"] == 1


def test_slo_is_met_only_when_p95_is_strictly_below_the_target():
    """El SLO se cumple solo si el p95 es estrictamente menor que la meta."""
    assert _filled([100], slo_p95_ms=101).snapshot()["slo"] == {
        "p95_ms_target": 101,
        "met": True,
    }
    assert _filled([100], slo_p95_ms=100).snapshot()["slo"]["met"] is False
