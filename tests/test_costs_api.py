"""Pruebas de la ventana de historial y de las llamadas cacheadas por la API."""

import json

from app.llm import ModelResponse


class RecordingModel:  # pylint: disable=too-few-public-methods
    """Modelo de prueba: responde fijo y guarda los mensajes recibidos.

    Solo imita la interfaz de un modelo (``complete``); no necesita mas metodos.
    """

    def __init__(self, cached=False):
        self.seen = []
        self._cached = cached

    def complete(self, messages):
        """Registra la conversacion y devuelve una respuesta directa."""
        self.seen.append([dict(m) for m in messages])
        return ModelResponse(
            text=json.dumps({"answer": "Listo"}),
            input_tokens=10,
            output_tokens=5,
            cached=self._cached,
        )


def test_only_the_last_history_messages_reach_the_model(make_cost_client):
    """Con HISTORY_WINDOW=2 solo los dos ultimos mensajes llegan al modelo."""
    model = RecordingModel()
    client = make_cost_client(model=model, HISTORY_WINDOW="2")
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"m{index}"}
        for index in range(4)
    ]
    response = client.post("/ask", json={"question": "Hola", "history": history})
    assert response.status_code == 200
    sent = model.seen[0]
    assert [m["content"] for m in sent] == ["m2", "m3", "Hola"]


def test_cached_call_is_counted_and_costs_nothing(make_cost_client):
    """Una llamada atendida desde cache se cuenta y no suma costo."""
    client = make_cost_client(model=RecordingModel(cached=True))
    body = client.post("/ask", json={"question": "Hola"}).json()
    assert body["cached_calls"] == 1
    assert body["cost_usd"] == 0
    assert client.get("/metrics").json()["cost_usd"] == 0
