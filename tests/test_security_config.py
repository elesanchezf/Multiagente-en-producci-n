"""Pruebas unitarias de la configuracion de seguridad (sesion 4).

Supuestos de interfaz: ``Config.environment``, ``Config.api_keys`` (``dict``
cliente a clave, fuera de ``repr``) y ``Config.rate_limit_per_minute``.
Las claves son ficticias.
"""

import pytest

from app.config import ConfigError, load_config

KEY = "fake-key-acme-0000000000"


def test_security_settings_have_safe_defaults():
    """Por omision: desarrollo, sin claves y 30 peticiones por minuto."""
    config = load_config({})
    assert config.environment == "development"
    assert not config.api_keys
    assert config.rate_limit_per_minute == 30


def test_the_rate_limit_must_be_a_positive_integer():
    """El limite por minuto debe ser un entero positivo; si no, ConfigError."""
    assert load_config({"RATE_LIMIT_PER_MINUTE": "5"}).rate_limit_per_minute == 5
    for raw in ("0", "-3", "many", "2.5"):
        with pytest.raises(ConfigError) as error:
            load_config({"RATE_LIMIT_PER_MINUTE": raw})
        assert "RATE_LIMIT_PER_MINUTE" in str(error.value)


def test_the_configuration_text_never_contains_the_keys():
    """La representacion en texto de la configuracion no incluye las claves."""
    config = load_config({"API_KEYS": f"acme:{KEY}"})
    assert config.api_keys == {"acme": KEY}
    assert KEY not in repr(config)
    assert KEY not in str(config)
