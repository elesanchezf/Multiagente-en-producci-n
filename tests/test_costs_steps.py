"""Pasos de los escenarios Gherkin de costos (sesion 3)."""

import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import ConfigError, load_config
from app.gateway import ModelUnavailable

scenarios("features/costs.feature")


class AlwaysFailingModel:  # pylint: disable=too-few-public-methods
    """Modelo de prueba que simula una caida del proveedor.

    Solo imita la interfaz de un modelo (``complete``); no necesita mas metodos.
    """

    def complete(self, messages):
        """Falla siempre con el error controlado del producto."""
        raise ModelUnavailable("simulated outage")


@pytest.fixture(name="context")
def context_fixture():
    """Guarda el cliente y la ultima respuesta entre pasos."""
    return {}


@given("the assistant is running with the default cost levers")
def _running_default(context, make_cost_client):
    context["client"] = make_cost_client()


@given("the assistant is running with routing disabled")
def _running_without_routing(context, make_cost_client):
    context["client"] = make_cost_client(ROUTING="false")


@given("the assistant is running with a model that always fails")
def _running_with_failing_model(context, make_cost_client):
    context["client"] = make_cost_client(model=AlwaysFailingModel())


@when(parsers.re(r'the user asks "(?P<question>.*)"'))
def _ask(context, question):
    context["response"] = context["client"].post("/ask", json={"question": question})


@when("the service starts with the gateway provider and no Cloudflare variables")
def _start_gateway_without_credentials(context):
    try:
        load_config({"MODEL_PROVIDER": "gateway"})
    except ConfigError as error:
        context["start_error"] = error


@then(parsers.parse("the response status is {code:d}"))
def _status(context, code):
    assert context["response"].status_code == code


@then("the model used is the small model")
def _small_model(context):
    assert context["response"].json()["model"] == "small-test"


@then("the model used is the large model")
def _large_model(context):
    assert context["response"].json()["model"] == "large-test"


@then("the route reason is not empty")
def _route_reason(context):
    assert context["response"].json()["route"]


@then("the cost matches the tokens and the price of the model used")
def _cost_matches(context, prices_path):
    body = context["response"].json()
    prices = json.loads(prices_path.read_text(encoding="utf-8"))
    price = prices["models"][body["model"]]
    expected = (
        body["input_tokens"] * price["input"] + body["output_tokens"] * price["output"]
    ) / 1_000_000
    assert body["cost_usd"] > 0
    assert body["cost_usd"] == pytest.approx(expected)


@then(parsers.parse("the answer reports {n:d} cached calls"))
def _cached_calls(context, n):
    assert context["response"].json()["cached_calls"] == n


@then("the metrics cost equals the cost of the answer")
def _metrics_cost(context):
    metrics = context["client"].get("/metrics").json()
    assert metrics["cost_usd"] == pytest.approx(context["response"].json()["cost_usd"])


@then(parsers.parse('the error detail is "{detail}"'))
def _error_detail(context, detail):
    assert context["response"].json()["detail"] == detail


@then("the error carries the request id of the response")
def _error_request_id(context):
    response = context["response"]
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


@then(parsers.parse('the start fails naming the variable "{name}"'))
def _start_fails(context, name):
    assert name in str(context["start_error"])
