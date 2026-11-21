"""Pruebas unitarias de la configuracion nueva de la sesion 3."""

import pytest

from app.config import ConfigError, load_config


def test_cost_settings_have_the_documented_defaults():
    """Los ajustes de costo toman los valores por omision documentados."""
    config = load_config({})
    assert config.model_small == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert config.model_large == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert config.routing is True
    assert config.router_max_chars == 80
    assert config.history_window == 6
    assert config.model_max_tokens == 300
    assert config.model_temperature == 0
    assert config.cache_ttl_seconds == 0
    assert config.prices_path == "data/model_prices.json"
    assert config.cf_gateway_id == "default"
    assert config.cf_account_id == ""
    assert config.cf_api_token == ""


@pytest.mark.parametrize(
    "name, value",
    [
        ("ROUTING", "maybe"),
        ("ROUTER_MAX_CHARS", "abc"),
        ("HISTORY_WINDOW", "-1"),
        ("MODEL_MAX_TOKENS", "0"),
        ("MODEL_TEMPERATURE", "hot"),
        ("CACHE_TTL_SECONDS", "-5"),
    ],
)
def test_invalid_cost_settings_prevent_startup(name, value):
    """Cada ajuste de costo invalido lanza ConfigError al cargar."""
    with pytest.raises(ConfigError):
        load_config({name: value})


def test_zero_is_valid_for_the_window_and_the_cache():
    """El valor cero es valido para la ventana de historial y el TTL del cache."""
    config = load_config({"HISTORY_WINDOW": "0", "CACHE_TTL_SECONDS": "0"})
    assert config.history_window == 0
    assert config.cache_ttl_seconds == 0
