"""Pruebas unitarias del calculo de costo (precios por millon de tokens).

Supuesto de interfaz: ``Pricing.from_file(path)``,
``Pricing.cost(model, input_tokens, output_tokens, cached=False)`` y la
excepcion ``PricingError`` en ``app.pricing``.
"""

import pytest

from app.pricing import Pricing, PricingError


def test_cost_uses_the_price_of_each_model(prices_path):
    """El costo se calcula con el precio de cada modelo por millon de tokens."""
    pricing = Pricing.from_file(prices_path)
    small = pricing.cost("small-test", 1000, 500)
    large = pricing.cost("large-test", 1000, 500)
    assert small == pytest.approx((1000 * 1000.0 + 500 * 2000.0) / 1_000_000)
    assert large == pytest.approx(10 * small)


def test_cached_call_costs_nothing(prices_path):
    """Una llamada cacheada tiene costo cero."""
    pricing = Pricing.from_file(prices_path)
    assert pricing.cost("large-test", 1000, 500, cached=True) == 0


def test_model_without_price_is_reported(prices_path):
    """Un modelo sin precio en la tabla lanza PricingError."""
    pricing = Pricing.from_file(prices_path)
    with pytest.raises(PricingError):
        pricing.cost("unknown-model", 10, 10)


def test_invalid_price_file_is_reported(tmp_path):
    """Un archivo de precios con JSON invalido lanza PricingError."""
    broken = tmp_path / "model_prices.json"
    broken.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PricingError):
        Pricing.from_file(broken)


def test_reserve_price_is_conservative_and_never_changes_reported_cost():
    """La reserva usa el precio mayor; el costo informado usa el precio normal."""
    pricing = Pricing({"m": {"input": 0.05, "output": 0.3, "reserve_input": 0.10}})
    assert pricing.cost("m", 1_000_000, 0) == 0.05
    assert pricing.reserve_cost("m", 1_000_000, 0) == 0.10
    assert pricing.reserve_cost("m", 0, 1_000_000) == 0.3


def test_reserve_cost_without_margin_equals_normal_cost():
    """Sin campos de reserva, la reserva coincide con el precio normal."""
    pricing = Pricing({"m": {"input": 1.0, "output": 2.0}})
    assert pricing.reserve_cost("m", 10, 10) == pricing.cost("m", 10, 10)
    with pytest.raises(PricingError):
        pricing.reserve_cost("unknown", 1, 1)


def test_gemma_table_separates_reported_price_from_reserve_margin():
    """La tabla real usa 0,05 para resultados y 0,10 solo para reservar."""
    pricing = Pricing.from_file("data/model_prices.json")
    model = "@cf/google/gemma-4-26b-a4b-it"
    assert pricing.cost(model, 1_000_000, 0) == 0.05
    assert pricing.cost(model, 0, 1_000_000) == 0.30
    assert pricing.reserve_cost(model, 1_000_000, 0) == 0.10
