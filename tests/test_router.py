"""Pruebas unitarias del enrutador de modelos (palanca 1).

Supuesto de interfaz: ``choose_route(question, config)`` devuelve un objeto
con ``model`` (nombre elegido) y ``reason`` (motivo, texto no vacio).
"""

import pytest

from app.config import load_config
from app.router import choose_route

SMALL = "small-test"
LARGE = "large-test"
BASE_ENV = {"MODEL_SMALL": SMALL, "MODEL_LARGE": LARGE}


def make_config(**overrides):
    """Construye una configuracion con modelos de nombres ficticios."""
    return load_config({**BASE_ENV, **overrides})


@pytest.mark.parametrize(
    "question",
    [
        "Compara a Ana y Jorge",
        "RESUME el departamento",
        "Explica el puesto de EMP-0001",
        "¿Por qué EMP-0004 es líder?",
        "Analiza Finanzas",
        "Dame todos los empleados",
    ],
)
def test_each_keyword_routes_to_the_large_model(question):
    """Cada palabra clave de complejidad enruta la pregunta al modelo grande."""
    decision = choose_route(question, make_config())
    assert decision.model == LARGE
    assert decision.reason


def test_question_at_the_limit_stays_small_and_one_more_goes_large():
    """Una pregunta en el limite usa el modelo chico; con un caracter mas, el grande."""
    config = make_config(ROUTER_MAX_CHARS="80")
    at_limit = choose_route("a" * 80, config)
    over_limit = choose_route("a" * 81, config)
    assert at_limit.model == SMALL
    assert over_limit.model == LARGE
    assert at_limit.reason != over_limit.reason


def test_routing_disabled_always_uses_the_large_model():
    """Con el enrutamiento apagado siempre se usa el modelo grande."""
    decision = choose_route("¿Quién es EMP-0004?", make_config(ROUTING="false"))
    assert decision.model == LARGE
    assert decision.reason
