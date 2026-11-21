"""Pasos de los escenarios Gherkin de observabilidad."""

import json
import re
import socket
import uuid
from datetime import datetime, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.clock import FixedClock, SteppingClock

scenarios("features/observability.feature")

QUESTION = "¿Quién es EMP-0004?"
FAILURE_MESSAGE = "secret failure detail"
START = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class FailingModel:  # pylint: disable=too-few-public-methods
    """Modelo de prueba que siempre truena con un mensaje reconocible.

    Solo imita la interfaz de un modelo (``complete``); no necesita mas metodos.
    """

    def complete(self, messages):
        """Falla siempre con un RuntimeError de mensaje reconocible."""
        raise RuntimeError(FAILURE_MESSAGE)


@pytest.fixture(name="context")
def context_fixture():
    """Guarda cliente, respuestas y texto del log entre pasos."""
    return {"responses": [], "log_text": ""}


@pytest.fixture(autouse=True)
def _capture_from_the_start(capsys):
    """Activa capsys antes del primer paso, para que el log del When quede capturado."""
    return capsys


def _lines(context, capsys):
    """Acumula la salida estandar y devuelve las lineas JSON del log."""
    context["log_text"] += capsys.readouterr().out
    return [json.loads(line) for line in context["log_text"].splitlines() if line]


def _events(context, capsys, name):
    return [line for line in _lines(context, capsys) if line["event"] == name]


@given("the observed assistant is running")
def _running(context, make_observed_client):
    context["client"] = make_observed_client()


@given("the observed assistant is running with a fixed clock")
def _running_fixed(context, make_observed_client):
    context["client"] = make_observed_client(clock=FixedClock(START))


@given("the observed assistant is running with a failing model")
def _running_failing(context, make_observed_client):
    context["client"] = make_observed_client(model=FailingModel())


@given(
    parsers.parse(
        "the observed assistant is running with a slow clock and a target of "
        "{target:d} ms"
    )
)
def _running_slow(context, make_observed_client, target):
    clock = SteppingClock(START, step_seconds=3)
    context["client"] = make_observed_client(clock=clock, slo_p95_ms=target)


@given("the observed assistant is running without a LangSmith key")
def _running_without_key(context, make_observed_client, monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    context["client"] = make_observed_client(tracing=True)


@given("any network connection is forbidden")
def _forbid_network(monkeypatch):
    loopback = {"127.0.0.1", "::1"}
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _is_loopback(address):
        # TestClient usa socketpair() en Windows, que conecta a loopback.
        return isinstance(address, tuple) and address[0] in loopback

    def _refuse(original):
        def guard(self, address, *args, **kwargs):
            if _is_loopback(address):
                return original(self, address, *args, **kwargs)
            raise AssertionError("a network connection was attempted")

        return guard

    monkeypatch.setattr(socket.socket, "connect", _refuse(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse(original_connect_ex))


@when(parsers.parse('the client requests "{path}"'))
def _get(context, path):
    context["responses"].append(context["client"].get(path))


@when(parsers.re(r"the client requests each of (?P<paths>.+)"))
def _get_each(context, paths):
    for path in re.findall(r'"([^"]+)"', paths):
        context["responses"].append(context["client"].get(path))


@when(parsers.re(r'the user asks "(?P<question>[^"]*)"$'))
def _ask(context, question):
    response = context["client"].post("/ask", json={"question": question})
    context["responses"].append(response)


@when(parsers.parse('the user asks "{question}" with the request id "{request_id}"'))
def _ask_with_id(context, question, request_id):
    response = context["client"].post(
        "/ask",
        json={"question": question},
        headers={"X-Request-ID": request_id},
    )
    context["responses"].append(response)


def _last(context):
    return context["responses"][-1]


@then(parsers.parse("the response status is {code:d}"))
def _status(context, code):
    assert _last(context).status_code == code


@then(parsers.parse('the X-Request-ID header is "{value}"'))
def _header_value(context, value):
    assert _last(context).headers["X-Request-ID"] == value


@then(parsers.parse('the response body request_id is "{value}"'))
def _body_id(context, value):
    assert _last(context).json()["request_id"] == value


@then("every response has a generated X-Request-ID header")
def _every_header(context):
    assert len(context["responses"]) == 4
    assert context["responses"][-1].status_code == 404
    for response in context["responses"]:
        assert uuid.UUID(response.headers["X-Request-ID"])


@then(
    parsers.parse(
        'the log has one "request" event with method "{method}", '
        'path "{path}" and status {status:d}'
    )
)
def _request_event(context, capsys, method, path, status):
    events = _events(context, capsys, "request")
    assert len(events) == 1
    assert (events[0]["method"], events[0]["path"]) == (method, path)
    assert events[0]["status"] == status


@then(
    'every log line has ts in UTC, service "hr-assistant", event and request_id'
)
def _common_fields(context, capsys):
    lines = _lines(context, capsys)
    assert lines
    for line in lines:
        stamp = datetime.fromisoformat(line["ts"].replace("Z", "+00:00"))
        assert stamp.utcoffset().total_seconds() == 0
        assert line["service"] == "hr-assistant"
        assert line["event"] and line["request_id"]


@then(parsers.parse("the request event has latency_ms {value:d}"))
def _latency(context, capsys, value):
    assert _events(context, capsys, "request")[0]["latency_ms"] == value


@then(
    parsers.parse(
        'the log has an "agent_run" event with {steps:d} steps and tools "{tool}"'
    )
)
def _agent_run(context, capsys, steps, tool):
    events = _events(context, capsys, "agent_run")
    assert len(events) == 1
    assert events[0]["steps"] == steps
    assert events[0]["tools"] == [tool]
    assert events[0]["request_id"] == "demo-123"


@then(
    parsers.parse(
        'the log has an "audit" event with action "{action}" and tool "{tool}"'
    )
)
def _audit(context, capsys, action, tool):
    events = _events(context, capsys, "audit")
    assert len(events) == 1
    assert (events[0]["action"], events[0]["tool"]) == (action, tool)
    assert events[0]["argument_names"] == ["employee_id"]
    assert "args" not in events[0]


@then("no log line contains the question text")
def _no_question(context, capsys):
    _lines(context, capsys)
    assert QUESTION not in context["log_text"]


@then("no log line contains the answer text")
def _no_answer(context, capsys):
    _lines(context, capsys)
    answer = _last(context).json()["answer"]
    assert "Jorge Díaz" in answer
    assert "Jorge Díaz" not in context["log_text"]


@then(
    parsers.parse(
        'the response body is "{detail}" with request_id "{request_id}"'
    )
)
def _error_body(context, detail, request_id):
    assert _last(context).json() == {"detail": detail, "request_id": request_id}


@then(parsers.parse('the log has an "error" event with the type "{error_type}"'))
def _error_event(context, capsys, error_type):
    events = _events(context, capsys, "error")
    assert len(events) == 1
    assert error_type in json.dumps(events[0])


@then("no log line contains the failure message")
def _no_failure_message(context, capsys):
    _lines(context, capsys)
    assert FAILURE_MESSAGE not in context["log_text"]


@then("the metrics have the documented shape")
def _metrics_shape(context):
    body = _last(context).json()
    assert set(body) == {
        "pid", "requests", "error_rate", "latency_ms", "tokens", "slo",
        "cost_usd",
    }
    assert set(body["latency_ms"]) == {"p50", "p95"}
    assert set(body["tokens"]) == {"input", "output"}
    assert set(body["slo"]) == {"p95_ms_target", "met"}
    assert body["requests"] >= 1


@then("the SLO is met")
def _slo_met(context):
    assert _last(context).json()["slo"]["met"] is True


@then("the SLO is not met")
def _slo_not_met(context):
    slo = _last(context).json()["slo"]
    assert slo["p95_ms_target"] == 2000
    assert slo["met"] is False
