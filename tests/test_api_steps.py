"""Pasos de los escenarios Gherkin de la API y de la pagina web."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.agent import STEP_LIMIT_ANSWER

scenarios("features/ask.feature", "features/web.feature")


@pytest.fixture(name="context")
def context_fixture():
    """Guarda el cliente y la ultima respuesta entre pasos."""
    return {}


@given("the assistant is running with the demo directory")
def _running(context, make_client):
    context["client"] = make_client()


@given(parsers.parse("the assistant is running with a limit of {n:d} step"))
def _running_with_step_limit(context, make_client, n):
    context["client"] = make_client(max_steps=n)


@given(parsers.parse("the assistant is running with a limit of {n:d} characters"))
def _running_with_question_limit(context, make_client, n):
    context["client"] = make_client(max_chars=n)


@when(parsers.re(r'the user asks "(?P<question>.*)"'))
def _ask(context, question):
    context["response"] = context["client"].post("/ask", json={"question": question})


@when(parsers.parse("the user asks a question of {n:d} characters"))
def _ask_long(context, n):
    context["response"] = context["client"].post("/ask", json={"question": "a" * n})


@when(parsers.parse('the client requests "{path}"'))
def _get(context, path):
    context["response"] = context["client"].get(path)


@then(parsers.parse("the response status is {code:d}"))
def _status(context, code):
    assert context["response"].status_code == code


@then(parsers.parse('the answer mentions "{text}"'))
def _answer_mentions(context, text):
    assert text in context["response"].json()["answer"]


@then(parsers.parse('the answer does not mention "{text}"'))
def _answer_not_mentions(context, text):
    assert text not in context["response"].json()["answer"]


@then(parsers.parse('the tools used are "{tool}"'))
def _tools(context, tool):
    assert context["response"].json()["tools_used"] == [tool]


@then("no tools were used")
def _no_tools(context):
    assert context["response"].json()["tools_used"] == []


@then(parsers.re(r"the agent took (?P<n>\d+) steps?"))
def _steps(context, n):
    assert context["response"].json()["steps"] == int(n)


@then("the answer is the step limit message")
def _limit_message(context):
    assert context["response"].json()["answer"] == STEP_LIMIT_ANSWER


@then(parsers.parse('the health status is "{status}" and includes a numeric pid'))
def _health(context, status):
    body = context["response"].json()
    assert body["status"] == status
    assert isinstance(body["pid"], int)


@then(parsers.parse('the page has the test id "{test_id}"'))
def _test_id(context, test_id):
    assert f'data-testid="{test_id}"' in context["response"].text


@then(parsers.parse('the page has the test ids "{a}", "{b}" and "{c}"'))
def _test_ids(context, a, b, c):
    page = context["response"].text
    for test_id in (a, b, c):
        assert f'data-testid="{test_id}"' in page
