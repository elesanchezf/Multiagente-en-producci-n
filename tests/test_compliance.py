"""Pruebas unitarias de las reglas de compliance (sesion 4).

Supuesto de interfaz: ``app.compliance.check_production(config)`` es una
funcion pura que devuelve la lista de reglas incumplidas (``list[str]``) y
una lista vacia si la configuracion es aceptable. Cada mensaje nombra la
variable afectada y nunca incluye valores. Si ``config.environment`` no es
``production`` devuelve siempre una lista vacia. Claves ficticias.
"""

from app.compliance import check_production
from app.config import load_config

KEY_16 = "fake-" + "0" * 11
KEY_15 = "fake-" + "0" * 10
assert (len(KEY_16), len(KEY_15)) == (16, 15)

PRODUCTION = {
    "ENVIRONMENT": "production",
    "MODEL_PROVIDER": "gateway",
    "CF_ACCOUNT_ID": "fake-account",
    "CF_API_TOKEN": "fake-cloudflare-token",
    "API_KEYS": f"acme:{KEY_16}",
}


def _check(**overrides):
    env = {**PRODUCTION, **overrides}
    return check_production(load_config(env))


def test_each_production_rule_is_reported_by_name_without_values():
    """Cada regla incumplida en produccion se nombra sin exponer valores."""
    cases = [
        ("MODEL_PROVIDER", {"MODEL_PROVIDER": "fake"}),
        ("API_KEYS", {"API_KEYS": ""}),
        ("API_KEYS", {"API_KEYS": f"acme:{KEY_15}"}),
        ("HIDE_INPUTS", {"LANGSMITH_TRACING": "true", "HIDE_INPUTS": "false"}),
        ("HIDE_OUTPUTS", {"LANGSMITH_TRACING": "true", "HIDE_OUTPUTS": "false"}),
    ]
    for variable, overrides in cases:
        violations = _check(**overrides)
        assert len(violations) == 1, overrides
        assert variable in violations[0]
        assert KEY_15 not in violations[0]
        assert "fake-cloudflare-token" not in violations[0]


def test_a_compliant_production_setup_has_no_violations():
    """Una configuracion de produccion que cumple las reglas no reporta nada."""
    assert len(_check()) == 0
    assert len(_check(API_KEYS=f"acme:{KEY_16},globex:{KEY_16}x")) == 0
    traced_and_hidden = _check(LANGSMITH_TRACING="true", HIDE_INPUTS="true")
    assert len(traced_and_hidden) == 0
    assert len(_check(LANGSMITH_TRACING="false", HIDE_INPUTS="false")) == 0


def test_development_has_no_restrictions():
    """En desarrollo no se aplica ninguna regla de produccion."""
    env = {
        "ENVIRONMENT": "development",
        "MODEL_PROVIDER": "fake",
        "API_KEYS": "acme:short",
        "LANGSMITH_TRACING": "true",
        "HIDE_INPUTS": "false",
    }
    assert len(check_production(load_config(env))) == 0
