"""Pruebas unitarias de la configuracion por variables de entorno."""

import pytest

from app.config import ConfigError, load_config


def test_defaults_are_used_when_nothing_is_set():
    """Sin variables de entorno se usan los valores por omision."""
    config = load_config({})
    assert config.model_provider == "fake"
    assert config.agent_max_steps == 3
    assert config.max_question_chars == 2000
    assert config.employees_path == "data/employees.json"


def test_environment_values_override_the_defaults():
    """Las variables de entorno reemplazan los valores por omision."""
    config = load_config(
        {
            "MODEL_PROVIDER": "fake",
            "AGENT_MAX_STEPS": "5",
            "MAX_QUESTION_CHARS": "100",
            "EMPLOYEES_PATH": "other/people.json",
        }
    )
    assert config.agent_max_steps == 5
    assert config.max_question_chars == 100
    assert config.employees_path == "other/people.json"


def test_observability_defaults_are_safe():
    """Por omision la observabilidad oculta entradas y salidas y no traza."""
    config = load_config({})
    assert config.service_name == "hr-assistant"
    assert config.slo_p95_ms == 2000
    assert config.langsmith_tracing is False
    assert config.hide_inputs is True
    assert config.hide_outputs is True


def test_observability_values_can_be_overridden():
    """Los valores de observabilidad se pueden cambiar por entorno."""
    config = load_config(
        {
            "SERVICE_NAME": "hr-test",
            "SLO_P95_MS": "500",
            "LANGSMITH_TRACING": "true",
            "HIDE_INPUTS": "false",
            "HIDE_OUTPUTS": "false",
        }
    )
    assert config.service_name == "hr-test"
    assert config.slo_p95_ms == 500
    assert config.langsmith_tracing is True
    assert config.hide_inputs is False
    assert config.hide_outputs is False


def test_invalid_values_prevent_startup():
    """Un valor invalido en el entorno lanza ConfigError al cargar."""
    invalid_environments = [
        {"AGENT_MAX_STEPS": "0"},
        {"AGENT_MAX_STEPS": "many"},
        {"MAX_QUESTION_CHARS": "-1"},
        {"MODEL_PROVIDER": "unknown-provider"},
        {"SLO_P95_MS": "0"},
        {"SLO_P95_MS": "fast"},
    ]
    for env in invalid_environments:
        with pytest.raises(ConfigError):
            load_config(env)
