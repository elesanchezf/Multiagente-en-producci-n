"""End-to-end tests of the HR assistant page, driven from the browser."""
import os
import re

from playwright.sync_api import Page, expect

FIRST_QUESTION = "How many vacation days do I get per year?"
SECOND_QUESTION = "And how do I request them?"
WRONG_KEY = "fictitious-wrong-key-0000"
INVALID_KEY_MESSAGE = "Clave inválida"


def enter_key(page: Page, key: str) -> None:
    """Type the API key in the key field."""
    page.get_by_test_id("api-key").fill(key)


def ask(page: Page, question: str, key: str | None = None) -> None:
    """Type the key (the valid one by default) and a question, then send it."""
    enter_key(page, os.environ["E2E_API_KEY"] if key is None else key)
    page.get_by_test_id("question").fill(question)
    page.get_by_test_id("send").click()


def test_user_sees_the_answer_after_asking_a_question(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text(FIRST_QUESTION)
    expect(page.get_by_test_id("answer").locator(".assistant")).to_have_count(1)


def test_user_sees_the_request_id_after_asking_a_question(page: Page):
    page.goto("/")
    expect(page.get_by_test_id("request-id")).to_have_text("-")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("request-id")).not_to_have_text("-")
    expect(page.get_by_test_id("request-id")).not_to_be_empty()


def test_question_field_is_cleared_after_sending(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("question")).to_have_value("")


def test_empty_question_shows_an_error_message_in_spanish(page: Page):
    page.goto("/")
    ask(page, "   ")
    expect(page.get_by_test_id("answer")).to_contain_text(
        re.compile(r"pregunta|vac[ií]a|error", re.IGNORECASE)
    )


def test_second_question_keeps_the_previous_conversation_on_screen(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("answer").locator(".assistant")).to_have_count(1)
    ask(page, SECOND_QUESTION)
    expect(page.get_by_test_id("answer").locator(".assistant")).to_have_count(2)
    expect(page.get_by_test_id("answer")).to_contain_text(FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text(SECOND_QUESTION)


def test_wrong_key_shows_the_invalid_key_message(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION, key=WRONG_KEY)
    expect(page.get_by_test_id("answer")).to_contain_text(INVALID_KEY_MESSAGE)
    expect(page.get_by_test_id("answer").locator(".assistant")).to_have_count(0)
