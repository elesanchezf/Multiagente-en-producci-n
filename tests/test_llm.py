"""Pruebas unitarias del modelo simulado y su protocolo JSON."""

import json

import pytest

from app.llm import FakeModel


@pytest.fixture(name="model")
def model_fixture(directory):
    """Modelo simulado construido sobre el directorio ficticio."""
    return FakeModel(directory)


def reply(model, text):
    """Envia un mensaje de usuario al modelo y devuelve su respuesta ya decodificada."""
    response = model.complete([{"role": "user", "content": text}])
    return json.loads(response.text)


def test_employee_id_requests_get_employee(model):
    """Un identificador de empleado en la pregunta pide la herramienta get_employee."""
    assert reply(model, "Dame datos de EMP-0004 por favor") == {
        "tool": "get_employee",
        "args": {"employee_id": "EMP-0004"},
    }


def test_known_department_requests_search_by_department(model):
    """Un departamento conocido pide la herramienta search_by_department."""
    result = reply(model, "¿Quiénes están en Finanzas?")
    assert result["tool"] == "search_by_department"
    assert result["args"] == {"department": "Finanzas"}


def test_tool_result_is_answered_before_other_rules(model):
    """Un resultado de herramienta se responde antes de aplicar otras reglas."""
    result = "EMP-0001 Finanzas"
    text = "Resultado de la herramienta: " + result
    assert reply(model, text) == {"answer": "Según el directorio: " + result}


def test_unmatched_question_gets_guidance_and_tokens_are_counted(model):
    """Una pregunta sin coincidencia recibe una guia y se cuentan los tokens."""
    messages = [
        {"role": "user", "content": "uno dos"},
        {"role": "assistant", "content": "tres"},
        {"role": "user", "content": "hola que tal"},
    ]
    response = model.complete(messages)
    assert json.loads(response.text) == {
        "answer": "Pregúntame por un empleado (EMP-0001) o un departamento."
    }
    assert response.input_tokens == 6
    assert response.output_tokens > 0
