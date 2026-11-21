"""Pruebas unitarias del adaptador de trazas opcionales.

Supuestos de interfaz: ``is_tracing_enabled(env)`` (verdadero solo con
``LANGSMITH_TRACING=true`` y una clave no vacia), ``traced(name, enabled)``
(decorador) y ``redact(value, hide)`` (reemplaza el valor si ``hide``).
"""

from app.tracing import is_tracing_enabled, redact, traced


def test_tracing_needs_both_the_flag_and_the_key():
    """La traza solo se activa con la bandera en true y una clave presente."""
    assert not is_tracing_enabled({})
    assert not is_tracing_enabled({"LANGSMITH_TRACING": "true"})
    assert not is_tracing_enabled({"LANGSMITH_API_KEY": "fake-key"})
    assert is_tracing_enabled(
        {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "fake-key"}
    )


def test_disabled_tracing_keeps_results_and_hidden_values_are_not_sent():
    """Sin traza el resultado no cambia y los valores ocultos no se envian."""
    @traced("add", enabled=False)
    def add(left, right=1):
        return left + right

    secret = "question about EMP-0004"
    assert add(2, right=3) == 5
    assert secret not in str(redact(secret, hide=True))
    assert redact(secret, hide=False) == secret
