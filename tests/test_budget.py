"""Pruebas del tope duro de presupuesto, sin red."""

import pytest

from app.budget import BudgetExceeded, BudgetGuard, BudgetedModel, wrap_models
from app.llm import ModelResponse
from app.pricing import Pricing

PRICES = Pricing({"m": {"input": 1000.0, "output": 2000.0}})
MESSAGES = [{"role": "user", "content": "a" * 100}]


class Echo:  # pylint: disable=too-few-public-methods
    """Modelo que cuenta llamadas y devuelve un consumo fijo."""

    def __init__(self, tokens=(10, 5), cached=False):
        self.calls = 0
        self._tokens = tokens
        self._cached = cached

    def complete(self, _messages):
        """Devuelve una respuesta fija."""
        self.calls += 1
        return ModelResponse("{}", *self._tokens, cached=self._cached)


def _guard(**overrides):
    values = {"max_calls": 4, "max_usd": 1.0, "max_input_tokens": 1000,
              "max_output_tokens": 10}
    values.update(overrides)
    return BudgetGuard(PRICES, **values)


def test_calls_are_limited_and_the_provider_is_not_reached():
    """Una llamada sobre el máximo se rechaza antes de enviarse."""
    guard = _guard(max_calls=2)
    inner = Echo()
    model = BudgetedModel(inner, "m", guard)
    model.complete(MESSAGES)
    model.complete(MESSAGES)
    with pytest.raises(BudgetExceeded):
        model.complete(MESSAGES)
    assert inner.calls == 2
    assert guard.calls == 2
    assert guard.tripped == "max_calls"


def test_input_estimate_is_conservative_and_capped_per_call():
    """La entrada se estima por caracteres y un exceso bloquea la llamada."""
    guard = _guard(max_input_tokens=50)
    assert guard.estimate_input(MESSAGES) == 108  # 100 bytes + 8 de margen
    accents = [{"role": "user", "content": "á" * 10}]
    assert guard.estimate_input(accents) == 28  # 2 bytes por carácter + 8
    inner = Echo()
    with pytest.raises(BudgetExceeded):
        BudgetedModel(inner, "m", guard).complete(MESSAGES)
    assert inner.calls == 0
    assert guard.tripped == "max_input_tokens"


def test_cost_is_reserved_before_and_accumulated_after_each_call():
    """El peor caso de la llamada no puede superar el tope en dólares."""
    # Reserva de la primera llamada: 108*1000/1e6 + 10*2000/1e6 = 0.128 USD.
    guard = _guard(max_usd=0.2, max_input_tokens=10000)
    inner = Echo(tokens=(10, 5))
    model = BudgetedModel(inner, "m", guard)
    model.complete(MESSAGES)
    assert guard.spent_usd == pytest.approx(10 * 1000 / 1e6 + 5 * 2000 / 1e6)
    assert guard.usage[0]["input_tokens"] == 10
    with pytest.raises(BudgetExceeded):
        model.complete(MESSAGES * 40)
    assert guard.tripped == "max_usd"
    assert inner.calls == 1


def test_cached_calls_are_free_and_failures_still_count_as_calls():
    """Una caché no cuesta; una llamada fallida consume el cupo y no se reintenta."""
    guard = _guard(max_calls=1)
    BudgetedModel(Echo(cached=True), "m", guard).complete(MESSAGES)
    assert guard.spent_usd == 0.0

    class Failing:  # pylint: disable=too-few-public-methods
        """Falla siempre."""

        def complete(self, _messages):
            """Simula un error del proveedor."""
            raise RuntimeError("fallo")

    second = _guard(max_calls=1)
    with pytest.raises(RuntimeError):
        BudgetedModel(Failing(), "m", second).complete(MESSAGES)
    assert second.calls == 1
    with pytest.raises(BudgetExceeded):
        BudgetedModel(Echo(), "m", second).complete(MESSAGES)


def test_wrap_models_shares_one_guard():
    """Todos los modelos comparten el mismo contador."""
    guard = _guard()
    wrapped = wrap_models({"m": Echo(), "n": Echo()}, guard)
    wrapped["m"].complete(MESSAGES)
    assert guard.calls == 1
    assert set(wrapped) == {"m", "n"}
