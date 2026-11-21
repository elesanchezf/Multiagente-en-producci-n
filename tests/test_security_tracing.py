"""Prueba de que la traza lleva el cliente y nunca su clave (sesion 4).

Se sustituye ``langsmith`` por un doble de prueba: no hay red ni claves reales.
Supuesto de interfaz: los metadatos de la traza incluyen ``client`` y
``request_id``.
"""

import app.tracing as tracing_module


class FakeRunTree:  # pylint: disable=too-few-public-methods
    """Arbol de ejecucion de prueba que solo guarda metadatos.

    Es un contenedor de datos: la prueba solo lee su atributo ``metadata``.
    """

    def __init__(self):
        self.metadata = {}


def test_trace_metadata_has_the_client_name_and_not_the_key(
    monkeypatch, make_secure_client, client_keys
):
    """Los metadatos de la traza llevan el nombre del cliente y no su clave."""
    tree = FakeRunTree()

    def fake_traceable(**_options):
        return lambda func: func

    monkeypatch.setenv("LANGSMITH_API_KEY", "fake-langsmith-key")
    monkeypatch.setattr(
        tracing_module, "_load_traceable", lambda: (fake_traceable, lambda: tree)
    )
    client = make_secure_client(LANGSMITH_TRACING="true")

    response = client.post(
        "/ask",
        json={"question": "¿Quién es EMP-0004?"},
        headers={"X-API-Key": client_keys["globex"]},
    )

    assert response.status_code == 200
    assert tree.metadata["client"] == "globex"
    assert tree.metadata["request_id"]
    assert client_keys["globex"] not in str(tree.metadata)
