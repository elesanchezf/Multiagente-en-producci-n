"""Pruebas unitarias del modelo real con un transporte httpx simulado.

Supuesto de interfaz: ``GatewayModel(config, model_name, transport=None)``
en ``app.gateway``, con ``complete(messages)`` que devuelve ``ModelResponse``
(con el atributo ``cached``), y la excepcion ``ModelUnavailable``. Ninguna
prueba usa la red; las credenciales son ficticias.
"""

import json

import httpx
import pytest

from app.config import load_config
from app.gateway import GatewayModel, ModelUnavailable, REQUEST_TIMEOUT_SECONDS

FAKE_TOKEN = "token-for-tests-only"
EXPECTED_URL = (
    "https://gateway.ai.cloudflare.com/v1/test-account/test-gateway"
    "/workers-ai/v1/chat/completions"
)
MESSAGES = [{"role": "user", "content": "Hola"}]
OK_BODY = {
    "choices": [{"message": {"role": "assistant", "content": '{"answer": "Hola"}'}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 7},
}


def make_model(handler, **overrides):
    """Crea un GatewayModel cuyo transporte ejecuta ``handler``."""
    env = {
        "MODEL_PROVIDER": "gateway",
        "CF_ACCOUNT_ID": "test-account",
        "CF_GATEWAY_ID": "test-gateway",
        "CF_API_TOKEN": FAKE_TOKEN,
        "MODEL_MAX_TOKENS": "123",
        "MODEL_TEMPERATURE": "0",
        **overrides,
    }
    transport = httpx.MockTransport(handler)
    return GatewayModel(load_config(env), "small-test", transport=transport)


def test_request_has_the_expected_url_credentials_and_body():
    """La peticion usa la URL, la credencial y el cuerpo esperados."""
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json=OK_BODY)

    make_model(handler).complete(MESSAGES)
    request = seen["request"]
    body = json.loads(request.content)
    assert str(request.url) == EXPECTED_URL
    assert request.headers["Authorization"] == f"Bearer {FAKE_TOKEN}"
    assert "cf-aig-cache-ttl" not in request.headers
    assert body == {
        "model": "small-test",
        "messages": MESSAGES,
        "max_tokens": 123,
        "temperature": 0,
    }


def test_text_and_tokens_are_read_from_the_response():
    """El texto y los tokens se leen de la respuesta del gateway."""
    model = make_model(lambda request: httpx.Response(200, json=OK_BODY))
    response = model.complete(MESSAGES)
    assert response.text == '{"answer": "Hola"}'
    assert (response.input_tokens, response.output_tokens) == (12, 7)
    assert response.cached is False


def test_cache_ttl_is_sent_and_a_hit_is_reported():
    """El TTL del cache se envia en la cabecera y un HIT se marca como cacheado."""
    seen = {}

    def handler(request):
        seen["ttl"] = request.headers.get("cf-aig-cache-ttl")
        return httpx.Response(
            200, json=OK_BODY, headers={"cf-aig-cache-status": "HIT"}
        )

    response = make_model(handler, CACHE_TTL_SECONDS="60").complete(MESSAGES)
    assert seen["ttl"] == "60"
    assert response.cached is True


def test_http_error_becomes_model_unavailable_without_leaking_the_token():
    """Un error HTTP se convierte en ModelUnavailable sin mostrar el token."""
    model = make_model(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(ModelUnavailable) as error:
        model.complete(MESSAGES)
    assert FAKE_TOKEN not in str(error.value)


def test_timeout_becomes_model_unavailable():
    """Un tiempo de espera agotado se convierte en ModelUnavailable."""
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(ModelUnavailable):
        make_model(handler).complete(MESSAGES)


def test_invalid_json_becomes_model_unavailable():
    """Una respuesta que no es JSON se convierte en ModelUnavailable."""
    model = make_model(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(ModelUnavailable):
        model.complete(MESSAGES)


def test_extra_params_are_sent_only_for_the_configured_model():
    """Los parámetros por modelo viajan solo con ese modelo y no pisan los base."""
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    extra = {"gemma": {"chat_template_kwargs": {"enable_thinking": False},
                       "response_format": {"type": "json_object"}}}
    config = load_config({
        "MODEL_PROVIDER": "gateway", "CF_ACCOUNT_ID": "a" * 32,
        "CF_API_TOKEN": "token-ficticio-0000",
        "MODEL_EXTRA_PARAMS": json.dumps(extra)})
    transport = httpx.MockTransport(handler)
    messages = [{"role": "user", "content": "x"}]
    GatewayModel(config, "gemma", transport).complete(messages)
    GatewayModel(config, "otro", transport).complete(messages)
    assert bodies[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert bodies[0]["model"] == "gemma"
    assert bodies[0]["max_tokens"] == config.model_max_tokens
    assert "chat_template_kwargs" not in bodies[1]
    assert "response_format" not in bodies[1]


def test_timeout_message_names_the_exception_type_without_secrets():
    """El motivo identifica el tipo de excepción, sin texto de la excepción."""
    def handler(request):
        raise httpx.ReadTimeout("secret-detail", request=request)

    with pytest.raises(ModelUnavailable) as error:
        make_model(handler).complete(MESSAGES)
    assert str(error.value) == "Gateway request failed: ReadTimeout"


def test_request_timeout_leaves_room_for_slow_model_calls():
    """El tope de espera es de 60 s (hubo una llamada de 30 s con Gemma)."""
    assert REQUEST_TIMEOUT_SECONDS == 60.0
