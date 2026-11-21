"""Pasos de los escenarios Gherkin de acceso seguro (sesion 4).

Todas las claves y los nombres de cliente son ficticios.
"""

import json
import re

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import ConfigError

scenarios("features/security.feature")

PROTECTED = (("POST", "/ask"), ("GET", "/metrics"))
INVALID_DETAIL = {"detail": "invalid or missing API key"}


@pytest.fixture(name="context")
def context_fixture():
    """Guarda cliente, respuestas, texto del log y error de arranque."""
    return {"responses": [], "log_text": "", "error": None}


@pytest.fixture(autouse=True)
def _capture_from_the_start(capsys):
    """Activa capsys antes del primer paso para capturar el log del When."""
    return capsys


def _events(context, capsys, name):
    context["log_text"] += capsys.readouterr().out
    lines = [json.loads(line) for line in context["log_text"].splitlines() if line]
    return [line for line in lines if line["event"] == name]


def _call(client, method, path, headers):
    if method == "POST":
        body = {"question": "¿Quién es EMP-0004?"}
        return client.post(path, json=body, headers=headers)
    return client.get(path, headers=headers)


@given("the secure assistant is running")
def _running(context, make_secure_client):
    context["client"] = make_secure_client()


@given(
    parsers.parse(
        "the secure assistant is running with a limit of {limit:d} requests per minute"
    )
)
def _running_limited(context, make_secure_client, manual_clock, limit):
    context["clock"] = manual_clock
    context["client"] = make_secure_client(
        clock=manual_clock, RATE_LIMIT_PER_MINUTE=str(limit)
    )


@when("the client calls the protected routes without a key")
def _without_key(context):
    context["responses"] = [
        _call(context["client"], method, path, {}) for method, path in PROTECTED
    ]


@when("the client calls the protected routes with an invalid key")
def _invalid_key(context):
    headers = {"X-API-Key": "fake-key-not-registered-00"}
    context["responses"] = [
        _call(context["client"], method, path, headers) for method, path in PROTECTED
    ]


@when(parsers.parse('the client "{name}" asks "{question}"'))
def _ask(context, client_keys, name, question):
    response = context["client"].post(
        "/ask",
        json={"question": question},
        headers={"X-API-Key": client_keys[name]},
    )
    context["responses"].append(response)


@when(parsers.parse('the client "{name}" asks {count:d} questions'))
def _ask_many(context, client_keys, name, count):
    for _ in range(count):
        _ask(context, client_keys, name, "¿Quién es EMP-0004?")


@when(parsers.parse("the clock advances {seconds:d} seconds"))
def _advance(context, seconds):
    context["clock"].advance(seconds)


@when("the assistant starts in production with the fake model and a valid key")
def _start_production_fake(context, make_secure_client):
    try:
        make_secure_client(ENVIRONMENT="production", MODEL_PROVIDER="fake")
    except ConfigError as error:
        context["error"] = error


@when(parsers.parse('the assistant starts with the key list "{raw}"'))
def _start_with_keys(context, make_secure_client, raw):
    try:
        make_secure_client(API_KEYS=raw)
    except ConfigError as error:
        context["error"] = error


@then(parsers.parse("the response status is {code:d}"))
def _status(context, code):
    assert context["responses"][-1].status_code == code


@then(parsers.parse('every response is 401 with the detail "{detail}"'))
def _every_401(context, detail):
    assert len(context["responses"]) == len(PROTECTED)
    for response in context["responses"]:
        assert response.status_code == 401
        assert response.json() == {"detail": detail}


@then(
    parsers.re(
        r'the public routes "(?P<first>[^"]+)", "(?P<second>[^"]+)" and '
        r'"(?P<third>[^"]+)" answer 200 without a key'
    )
)
def _public_routes(context, first, second, third):
    for path in (first, second, third):
        assert context["client"].get(path).status_code == 200


@then(
    parsers.parse(
        'the "request", "agent_run" and "audit" log events have the client "{name}"'
    )
)
def _client_in_log(context, capsys, name):
    for event in ("request", "agent_run", "audit"):
        found = _events(context, capsys, event)
        assert found, event
        assert all(item["client"] == name for item in found)


@then(parsers.parse('no log line contains the key of "{name}"'))
def _no_key_in_log(context, capsys, client_keys, name):
    _events(context, capsys, "request")
    assert context["log_text"]
    assert client_keys[name] not in context["log_text"]


@then(parsers.parse('the last response is 429 with the detail "{detail}"'))
def _rate_limited(context, detail):
    last = context["responses"][-1]
    assert last.status_code == 429
    assert last.json() == {"detail": detail}


@then("the Retry-After header is a positive number of seconds")
def _retry_after(context):
    assert int(context["responses"][-1].headers["Retry-After"]) >= 1


@then(parsers.parse('the client "{name}" can still ask a question'))
def _can_ask(context, client_keys, name):
    _ask(context, client_keys, name, "¿Quién es EMP-0004?")
    assert context["responses"][-1].status_code == 200


@then(parsers.parse('the start is refused and the message names "{variable}"'))
def _refused_names(context, variable):
    assert context["error"] is not None
    assert variable in str(context["error"])


@then(
    parsers.parse(
        "the start is refused and the message gives the length {length:d} "
        "of the failing entry"
    )
)
def _refused_length(context, length):
    assert context["error"] is not None
    assert re.search(rf"\b{length}\b", str(context["error"]))


@then("the message does not contain the key")
def _message_without_key(context, client_keys):
    for key in client_keys.values():
        assert key not in str(context["error"])


@then(parsers.parse('the message does not contain the text "{text}"'))
def _message_without_text(context, text):
    assert text not in str(context["error"])
