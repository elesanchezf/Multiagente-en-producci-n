"""Contratos de colaboración, revisión cerrada y aislamiento entre solicitudes."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agent import RunSettings, STEP_LIMIT_ANSWER
from app.llm import FakeModel, GUIDANCE_ANSWER, ModelResponse, ModelUnavailable
from app.multiagent import (
    Coordinator, DIRECTORY_PROMPT, REJECTED_ANSWER, REVIEW_PROMPT)
from app.pricing import Pricing


# Doble de un proveedor: una sola operación pública.
# pylint: disable-next=too-few-public-methods
class ReviewModel:
    """Controla el dictamen sin sustituir consultas reales al directorio de prueba."""

    def __init__(self, directory, verdict):
        self._fake = FakeModel(directory)
        self.verdict = verdict
        self.calls = []

    def complete(self, messages):
        """Devuelve el dictamen guionado únicamente al agente revisor."""
        self.calls.append(messages)
        if messages[0].get("content") == REVIEW_PROMPT:
            if isinstance(self.verdict, Exception):
                raise self.verdict
            return ModelResponse(self.verdict, 7, 3)
        return self._fake.complete(messages)


def test_consultation_is_reviewed_with_separate_context(directory):
    """El revisor recibe evidencia y borrador, sin heredar el historial de chat."""
    model = ReviewModel(directory, '{"approved":true}')
    result = Coordinator(model, directory, 3).run(
        "EMP-0004", [{"role": "user", "content": "historial privado"}]
    )
    assert result.agents_used == ["coordinator", "directory", "reviewer"]
    assert result.review_status == "approved"
    assert "Jorge Díaz" in result.answer
    assert result.review_calls == 1
    assert (result.review_input_tokens, result.review_output_tokens) == (7, 3)
    assert len(model.calls) == 3
    review = json.loads(model.calls[-1][-1]["content"])
    assert review["evidence"]
    assert "historial privado" not in json.dumps(model.calls[-1])


@pytest.mark.parametrize("verdict", [
    '{"approved":false}', '{"approved":"true"}', 'true', '[]',
    'not JSON', '{"approved":true,"answer":"inventado"}',
])
def test_review_rejects_negative_or_invalid_verdict(directory, verdict):
    """Una salida no conforme jamás se interpreta como aprobación."""
    result = Coordinator(ReviewModel(directory, verdict), directory, 3).run("EMP-0004")
    assert result.answer == REJECTED_ANSWER
    assert result.review_status == "rejected"


def test_review_failure_is_not_silently_approved(directory):
    """Un proveedor caído conserva la señal de error para la API."""
    model = ReviewModel(directory, ModelUnavailable("provider unavailable"))
    with pytest.raises(ModelUnavailable):
        Coordinator(model, directory, 3).run("EMP-0004")


def test_review_cost_and_tokens_are_included(directory, prices_path):
    """El total contiene consulta y revisión, incluyendo los precios del modelo."""
    model = ReviewModel(directory, '{"approved":true}')
    pricing = Pricing.from_file(prices_path)
    settings = RunSettings(model_name="small-test", pricing=pricing)
    result = Coordinator(model, directory, 3, settings=settings).run("EMP-0004")
    responses = [FakeModel(directory).complete(call) for call in model.calls[:-1]]
    expected_input = sum(item.input_tokens for item in responses) + 7
    expected_output = sum(item.output_tokens for item in responses) + 3
    assert result.input_tokens == expected_input
    assert result.output_tokens == expected_output
    assert result.cost_usd == pytest.approx(
        pricing.cost("small-test", expected_input, expected_output, False)
    )


def test_no_review_of_unfinished_directory_run(directory):
    """El límite del especialista se conserva y no se aprueban resultados parciales."""
    result = Coordinator(FakeModel(directory), directory, 1).run("EMP-0004")
    assert result.answer == STEP_LIMIT_ANSWER
    assert result.review_status == "skipped_incomplete"
    assert result.review_calls == 0


def test_unsubstantiated_direct_answer_is_rejected(directory):
    """Una afirmación libre sin consulta de herramientas no llega al usuario."""
    class InventedModel:  # pylint: disable=too-few-public-methods
        """Proveedor que inventa un salario sin consultar evidencia."""

        def complete(self, _messages):
            """Devuelve deliberadamente una afirmación no sustentada."""
            return ModelResponse('{"answer":"Gana un millón"}', 2, 3)

    result = Coordinator(InventedModel(), directory, 3).run("EMP-0004")
    assert result.answer == REJECTED_ANSWER
    assert result.review_status == "no_evidence"


def test_approved_draft_cannot_add_facts_outside_evidence(directory):
    """Incluso una aprobación errónea no publica prosa inventada del especialista."""
    # Doble de proveedor: conserva la única operación pública complete.
    class InventedDraft(ReviewModel):  # pylint: disable=too-few-public-methods
        """Introduce una afirmación falsa después de consultar la herramienta."""

        def complete(self, messages):
            """Simula un especialista que mezcla datos ciertos con un salario falso."""
            if messages[-1]["content"].startswith("Resultado de la herramienta:"):
                return ModelResponse('{"answer":"Jorge gana un millón"}', 2, 3)
            return super().complete(messages)

    result = Coordinator(
        InventedDraft(directory, '{"approved":true}'), directory, 3
    ).run("EMP-0004")
    assert "Jorge Díaz" in result.answer
    assert "millón" not in result.answer


def test_trace_hierarchy_and_transitions_do_not_log_content(directory):
    """Las fases quedan anidadas y los eventos propios no contienen preguntas."""
    stack, spans, events = [], [], []

    def trace(name):
        """Registra padres e hijos sin llamar a servicios externos."""
        def decorate(function):
            def wrapped(*args, **kwargs):
                spans.append((name, tuple(stack)))
                stack.append(name)
                try:
                    return function(*args, **kwargs)
                finally:
                    stack.pop()
            return wrapped
        return decorate

    class Logger:  # pylint: disable=too-few-public-methods
        """Captura eventos para verificar las transiciones."""

        def emit(self, event, **fields):
            """Guarda eventos en memoria."""
            events.append({"event": event, **fields})

    Coordinator(FakeModel(directory), directory, 3, Logger(), trace).run("EMP-0004")
    assert ("directory_agent", ("coordinator",)) in spans
    assert ("reviewer_agent", ("coordinator",)) in spans
    own_events = [e for e in events if e["event"] in {"handoff", "workflow_completed"}]
    assert len(own_events) == 3
    assert "Jorge" not in json.dumps(own_events)
    assert "EMP-0004" not in json.dumps(own_events)


def test_concurrent_requests_keep_their_evidence_separate(directory):
    """Ejecuciones simultáneas no mezclan los registros de dos empleados."""
    coordinator = Coordinator(FakeModel(directory), directory, 3)
    ids = ["EMP-0001", "EMP-0004"] * 10
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(coordinator.run, ids))
    for employee_id, result in zip(ids, results):
        other_id = "EMP-0004" if employee_id == "EMP-0001" else "EMP-0001"
        assert employee_id in result.answer
        assert other_id not in result.answer
        assert result.review_status == "approved"


def test_api_exposes_review_without_internal_evidence(make_client):
    """La API publica el estado de colaboración y oculta borradores internos."""
    response = make_client().post("/ask", json={"question": "EMP-0004"})
    assert response.status_code == 200
    body = response.json()
    assert body["agents_used"] == ["coordinator", "directory", "reviewer"]
    assert body["review_status"] == "approved"
    assert body["review_calls"] == 1
    assert body["review_input_tokens"] > 0
    assert 0 <= body["review_cost_usd"] <= body["cost_usd"]
    assert "evidence" not in body


def test_directory_prompt_embeds_the_official_guidance_from_its_single_source():
    """El prompt cita GUIDANCE_ANSWER dentro del JSON esperado, sin copia manual."""
    expected = json.dumps({"answer": GUIDANCE_ANSWER}, ensure_ascii=False)
    assert expected in DIRECTORY_PROMPT
    assert "saluda" in DIRECTORY_PROMPT and "capacidades" in DIRECTORY_PROMPT
    assert "Consulta herramientas antes de afirmar datos de empleados" in (
        DIRECTORY_PROMPT)


def test_greeting_answered_with_the_guidance_is_published(directory):
    """Un modelo que sigue el prompt devuelve la guía exacta y se publica."""
    class FollowsPrompt:  # pylint: disable=too-few-public-methods
        """Comprueba que el prompt trae el JSON de guía y lo devuelve."""

        def complete(self, messages):
            """Devuelve el JSON que el prompt indica para los saludos."""
            expected = json.dumps({"answer": GUIDANCE_ANSWER}, ensure_ascii=False)
            assert expected in messages[0]["content"]
            return ModelResponse(expected, 2, 3)

    result = Coordinator(FollowsPrompt(), directory, 3).run(
        "Hola, ¿qué puedes hacer?")
    assert result.answer == GUIDANCE_ANSWER
    assert result.review_calls == 0


def test_employee_question_without_evidence_is_still_rejected(directory):
    """La guía no abre una vía: datos de un empleado sin herramienta se rechazan."""
    class Unsupported:  # pylint: disable=too-few-public-methods
        """Afirma datos de un empleado sin consultar el directorio."""

        def complete(self, _messages):
            """Devuelve una afirmación sin evidencia."""
            return ModelResponse(
                '{"answer":"EMP-0001 es Ana López, analista de datos"}', 2, 3)

    result = Coordinator(Unsupported(), directory, 3).run("¿Quién es EMP-0001?")
    assert result.answer == REJECTED_ANSWER
    assert result.review_status == "no_evidence"
    assert result.review_calls == 0
