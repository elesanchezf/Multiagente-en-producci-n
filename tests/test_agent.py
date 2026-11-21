"""Pruebas unitarias del bucle del agente con un modelo falso inyectado."""

import json

from app.agent import STEP_LIMIT_ANSWER, Agent
from app.llm import ModelResponse

TOOL_PREFIX = "Resultado de la herramienta: "


class ScriptedModel:  # pylint: disable=too-few-public-methods
    """Modelo de prueba: devuelve respuestas guionadas y registra lo recibido.

    Solo imita la interfaz de un modelo (``complete``); no necesita mas metodos.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def complete(self, messages):
        """Registra los mensajes recibidos y devuelve la siguiente respuesta."""
        self.seen.append([dict(m) for m in messages])
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return ModelResponse(text=text, input_tokens=2, output_tokens=1)


def test_direct_answer_takes_one_step_and_no_tools(directory):
    """Una respuesta directa del modelo cuesta un paso y no usa herramientas."""
    model = ScriptedModel([{"answer": "Hola"}])
    result = Agent(model, directory, max_steps=3).run("Hola")
    assert result.answer == "Hola"
    assert result.steps == 1
    assert result.tools_used == []


def test_tool_result_is_sent_back_to_the_model(directory):
    """El resultado de la herramienta vuelve al modelo como mensaje de usuario."""
    model = ScriptedModel(
        [
            {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}},
            {"answer": "Es Jorge Díaz"},
        ]
    )
    history = [{"role": "user", "content": "Hola"}]
    result = Agent(model, directory, max_steps=3).run("¿EMP-0004?", history)
    assert result.answer == "Es Jorge Díaz"
    assert result.steps == 2
    assert result.tools_used == ["get_employee"]
    assert (result.input_tokens, result.output_tokens) == (4, 2)
    assert len(model.seen) == 2
    first_call, second_call = model.seen[0], model.seen[1]
    assert first_call[0] == history[0]
    assert second_call[-1]["role"] == "user"
    assert second_call[-1]["content"].startswith(TOOL_PREFIX)
    assert "Jorge Díaz" in second_call[-1]["content"]


def test_loop_stops_at_the_step_limit_with_the_exact_message(directory):
    """Al agotar los pasos el bucle se detiene con el mensaje de limite exacto."""
    ask_tool = {"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}
    model = ScriptedModel([ask_tool])
    result = Agent(model, directory, max_steps=2).run("EMP-0001")
    assert result.answer == (
        "No pude completar la respuesta. Intenta con una pregunta más concreta."
    )
    assert STEP_LIMIT_ANSWER == result.answer
    assert result.steps == 2
    assert len(model.seen) == 2


class RecordingLogger:
    """Logger de prueba: guarda los eventos como tuplas ``(evento, campos)``."""

    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        """Guarda un evento con sus campos."""
        self.events.append((event, fields))

    def of(self, name):
        """Devuelve los campos de los eventos con el nombre indicado."""
        return [fields for event, fields in self.events if event == name]


def test_each_tool_call_is_audited_and_the_run_is_summarised(directory):
    """Cada herramienta se audita y la corrida se resume sin datos personales."""
    model = ScriptedModel(
        [
            {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}},
            {"answer": "Es Jorge Díaz"},
        ]
    )
    logger = RecordingLogger()
    history = [{"role": "user", "content": "Hola"}]
    Agent(model, directory, max_steps=3, logger=logger).run("¿EMP-0004?", history)
    (audit,) = logger.of("audit")
    assert audit["action"] == "tool_call"
    assert audit["tool"] == "get_employee"
    assert audit["argument_names"] == ["employee_id"]
    assert "EMP-0004" not in str(logger.events)
    (run,) = logger.of("agent_run")
    assert run["question_chars"] == len("¿EMP-0004?")
    assert run["history_messages"] == 1
    assert run["steps"] == 2
    assert run["tools"] == ["get_employee"]
    assert (run["input_tokens"], run["output_tokens"]) == (4, 2)
    assert "¿EMP-0004?" not in str(logger.events)
    assert "Jorge Díaz" not in str(logger.events)


def test_agent_run_reports_how_the_loop_stopped(directory):
    """El resumen distingue si el bucle paso por el limite o por una respuesta."""
    ask_tool = {"tool": "get_employee", "args": {"employee_id": "EMP-0001"}}
    limited, answered = RecordingLogger(), RecordingLogger()
    Agent(ScriptedModel([ask_tool]), directory, 2, logger=limited).run("EMP-0001")
    Agent(ScriptedModel([{"answer": "Hola"}]), directory, 2, logger=answered).run("x")
    stopped_at_limit = limited.of("agent_run")[0]["stopped"]
    stopped_by_answer = answered.of("agent_run")[0]["stopped"]
    assert stopped_at_limit != stopped_by_answer
    assert len(limited.of("audit")) == 2
    assert answered.of("audit") == []


def test_invalid_model_output_is_a_controlled_failure(directory):
    """Una salida invalida del modelo da una respuesta controlada sin herramientas."""
    bad_outputs = [
        "this is not json",
        {"tool": "delete_everything", "args": {}},
        {"tool": "get_employee", "args": {}},
        {"unexpected": "shape"},
    ]
    for bad in bad_outputs:
        result = Agent(ScriptedModel([bad]), directory, max_steps=2).run("x")
        assert isinstance(result.answer, str) and result.answer
        assert result.tools_used == []
