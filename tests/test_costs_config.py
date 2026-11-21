"""Pruebas unitarias de la configuracion nueva de la sesion 3."""

import json

import pytest

from app.config import ConfigError, load_config


def test_cost_settings_have_the_documented_defaults():
    """Los ajustes de costo toman los valores por omision documentados."""
    config = load_config({})
    # Provisional: no hay modelo pequeño verificado en el catálogo de la cuenta.
    assert config.model_small == config.model_large
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


def test_model_extra_params_are_validated_with_a_closed_list():
    """Solo se admiten parámetros conocidos; los demás se rechazan sin eco."""
    ok = {"m": {"chat_template_kwargs": {"enable_thinking": False},
                "response_format": {"type": "json_object"}}}
    assert load_config({"MODEL_EXTRA_PARAMS": json.dumps(ok)}).model_extra_params == ok
    assert load_config({}).model_extra_params == {}
    bad = ["no es json", "[]", '{"m": []}', '{"m": {"max_tokens": {"a": 1}}}',
           '{"m": {"model": {"a": 1}}}',
           '{"m": {"chat_template_kwargs": {"enable_thinking": "no"}}}',
           '{"m": {"chat_template_kwargs": {"otro": true}}}',
           '{"m": {"response_format": {"type": "json_schema"}}}']
    for raw in bad:
        with pytest.raises(ConfigError) as error:
            load_config({"MODEL_EXTRA_PARAMS": raw})
        assert raw not in str(error.value)
