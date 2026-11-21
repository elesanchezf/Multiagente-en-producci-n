"""Pruebas con información ficticia para las fronteras de entrada y salida."""

import json

import pytest

from app.directory import EmployeeDirectory
from app.llm import ModelResponse
from app.privacy import sensitive_kinds, public_record, SensitiveDataError


@pytest.mark.parametrize("text,kind", [
    ("demo@example.invalid", "email"),
    ("+52 55 1234 5678", "phone"),
    ("GODE561231HDFRRN09", "curp"),
    ("ABC010101AB1", "rfc"),
    ("password=solo-ejemplo", "credential"),
    ("Bearer fictitious-token", "credential"),
    ("demo\u200b@example.invalid", "email"),
])
def test_sensitive_input_never_reaches_model(make_client, capsys, text, kind):
    """Una pregunta sensible se bloquea y el log conserva solo categorías."""
    class NeverCalled:  # pylint: disable=too-few-public-methods
        """Falla si el control permite llamar al proveedor."""

        def complete(self, _messages):
            """No debe ejecutarse para entradas bloqueadas."""
            raise AssertionError("Provider must not be called")

    response = make_client(model=NeverCalled()).post("/ask", json={"question": text})
    assert response.status_code == 422
    assert text not in response.text
    logs = capsys.readouterr().out
    assert text not in logs
    events = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    assert any(kind in event.get("categories", []) for event in events)


def test_history_is_checked_before_trimming(make_client):
    """El historial sensible también se rechaza aunque no sea la pregunta actual."""
    response = make_client().post("/ask", json={
        "question": "EMP-0004",
        "history": [{"role": "user", "content": "demo@example.invalid"}],
    })
    assert response.status_code == 422


def test_validation_errors_do_not_echo_private_values(make_client):
    """Un tipo inválido no provoca el eco de la entrada de Pydantic."""
    body = {"question": {"email": "x@example.invalid"}}
    response = make_client().post("/ask", json=body)
    assert response.status_code == 422
    assert "example.invalid" not in response.text


def test_sensitive_model_output_is_blocked_before_review(make_client, capsys):
    """Una salida escapada de JSON tampoco se devuelve ni se registra."""
    class PrivateModel:  # pylint: disable=too-few-public-methods
        """Simula un modelo que intenta revelar un correo ficticio."""

        def complete(self, _messages):
            """Incluye el símbolo arroba como escape para probar el parseo previo."""
            return ModelResponse('{"answer":"demo\\u0040example.invalid"}', 1, 1)

    client = make_client(model=PrivateModel())
    response = client.post("/ask", json={"question": "EMP-0004"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Sensitive information blocked"
    assert "example.invalid" not in response.text + capsys.readouterr().out


def test_private_directory_fields_are_not_sent_to_model():
    """Campos no autorizados se eliminan antes de componer evidencia."""
    record = {"id": "EMP-0001", "name": "Ejemplo", "email": "x@example.invalid",
              "salary": 99999, "password": "solo-ejemplo"}
    assert public_record(record) == {"id": "EMP-0001", "name": "Ejemplo"}


def test_sensitive_data_in_allowed_field_is_blocked():
    """La lista de campos no basta: también se inspeccionan sus valores."""
    with pytest.raises(SensitiveDataError):
        public_record({"id": "EMP-0001", "name": "x@example.invalid"})


def test_dates_and_employee_ids_are_allowed():
    """Fechas e identificadores de la demo no se confunden con teléfonos."""
    assert not sensitive_kinds(["2016-11-02", "EMP-0003", "Tecnología"])


def test_sensitive_record_does_not_reach_second_model_call(make_client, capsys):
    """Un registro sensible bloquea la solicitud antes de una segunda llamada."""
    class CountingModel:  # pylint: disable=too-few-public-methods
        """Pide la herramienta y registra cada llamada recibida."""

        def __init__(self):
            self.calls = []

        def complete(self, messages):
            """Primera llamada: pide el registro; cualquier otra queda anotada."""
            self.calls.append(messages)
            return ModelResponse(
                '{"tool":"get_employee","args":{"employee_id":"EMP-0004"}}', 1, 1
            )

    model = CountingModel()
    directory = EmployeeDirectory([{"id": "EMP-0004", "name": "x@example.invalid"}])
    response = make_client(model=model, employee_directory=directory).post(
        "/ask", json={"question": "EMP-0004"}
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Sensitive information blocked"
    assert len(model.calls) == 1
    assert "example.invalid" not in response.text + capsys.readouterr().out
