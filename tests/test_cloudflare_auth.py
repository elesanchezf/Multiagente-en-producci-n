"""Pruebas de la autenticacion doble con Cloudflare AI Gateway.

Contrato: ``Config.cf_aig_token`` (opcional, fuera de ``repr``) se lee de
``CF_AIG_TOKEN``; ``GatewayModel`` envia ``Authorization`` con el token de la
API y, si existe, ``cf-aig-authorization`` con el token del gateway;
``ModelUnavailable`` expone ``status_code``; el log del evento ``error``
incluye ``status_code`` y ``request_id`` sin datos sensibles.

Todas las credenciales y preguntas son ficticias y de prueba.
"""

import json

import httpx
import pytest

from app.config import load_config
from app.gateway import GatewayModel, ModelUnavailable

API_TOKEN = "api-token-for-tests-only"
AIG_TOKEN = "aig-token-for-tests-only"
CLOUDFLARE_BODY = "cloudflare-body-for-tests-only"
SECRET_QUESTION = "Pregunta ficticia de prueba EMP-0001"
REQUEST_ID = "request-id-for-tests"
MESSAGES = [{"role": "user", "content": "Hola"}]
OK_BODY = {
    "choices": [{"message": {"role": "assistant", "content": '{"answer": "Hola"}'}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
}
GATEWAY_ENV = {
    "MODEL_PROVIDER": "gateway",
    "CF_ACCOUNT_ID": "test-account",
    "CF_GATEWAY_ID": "test-gateway",
    "CF_API_TOKEN": API_TOKEN,
}


def make_model(handler, **overrides):
    """Crea un GatewayModel con transporte simulado y tokens ficticios."""
    env = {**GATEWAY_ENV, **overrides}
    transport = httpx.MockTransport(handler)
    return GatewayModel(load_config(env), "small-test", transport=transport)


def capture_headers(**overrides):
    """Hace una llamada exitosa y devuelve los encabezados enviados."""
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        return httpx.Response(200, json=OK_BODY)

    make_model(handler, **overrides).complete(MESSAGES)
    return seen["headers"]


class FailingModel:  # pylint: disable=too-few-public-methods
    """Modelo falso que siempre falla con un estado HTTP."""

    def __init__(self, status_code):
        self._status_code = status_code

    def complete(self, messages):
        """Lanza ModelUnavailable con el estado configurado."""
        raise ModelUnavailable(
            "simulated gateway failure", status_code=self._status_code
        )


# --- Configuracion ---------------------------------------------------------


def test_aig_token_is_read_from_the_environment():
    """CF_AIG_TOKEN se lee en cf_aig_token."""
    config = load_config({**GATEWAY_ENV, "CF_AIG_TOKEN": AIG_TOKEN})
    assert config.cf_aig_token == AIG_TOKEN


def test_aig_token_is_optional_for_a_valid_gateway_configuration():
    """Sin CF_AIG_TOKEN la configuracion del gateway es valida y el valor es vacio."""
    config = load_config(GATEWAY_ENV)
    assert config.cf_aig_token == ""
    assert config.model_provider == "gateway"


def test_tokens_never_appear_in_the_config_repr():
    """Ningun token aparece en repr(config)."""
    config = load_config({**GATEWAY_ENV, "CF_AIG_TOKEN": AIG_TOKEN})
    text = repr(config)
    assert AIG_TOKEN not in text
    assert API_TOKEN not in text


# --- Modelo del gateway ----------------------------------------------------


def test_each_token_goes_only_in_its_own_header():
    """Cada token viaja solo en su encabezado, sin intercambiarse."""
    headers = capture_headers(CF_AIG_TOKEN=AIG_TOKEN)
    assert headers["Authorization"] == f"Bearer {API_TOKEN}"
    assert headers["cf-aig-authorization"] == f"Bearer {AIG_TOKEN}"
    assert AIG_TOKEN not in headers["Authorization"]
    assert API_TOKEN not in headers["cf-aig-authorization"]


def test_without_an_aig_token_the_gateway_header_is_not_sent():
    """Con cf_aig_token vacio no se envia cf-aig-authorization."""
    headers = capture_headers()
    assert "cf-aig-authorization" not in headers
    assert headers["Authorization"] == f"Bearer {API_TOKEN}"


def test_an_empty_aig_token_value_behaves_like_a_missing_one():
    """Un CF_AIG_TOKEN vacio explicito tampoco genera el encabezado."""
    headers = capture_headers(CF_AIG_TOKEN="")
    assert "cf-aig-authorization" not in headers
    assert headers["Authorization"] == f"Bearer {API_TOKEN}"


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_error_status_is_kept_in_model_unavailable(status):
    """Un estado HTTP de error se conserva en status_code de la excepcion."""
    model = make_model(
        lambda request: httpx.Response(status, text=CLOUDFLARE_BODY),
        CF_AIG_TOKEN=AIG_TOKEN,
    )
    with pytest.raises(ModelUnavailable) as error:
        model.complete(MESSAGES)
    assert error.value.status_code == status


@pytest.mark.parametrize("status", [401, 500])
def test_error_message_never_contains_tokens_or_the_response_body(status):
    """El mensaje de la excepcion no incluye tokens ni el cuerpo de Cloudflare."""
    model = make_model(
        lambda request: httpx.Response(status, text=CLOUDFLARE_BODY),
        CF_AIG_TOKEN=AIG_TOKEN,
    )
    with pytest.raises(ModelUnavailable) as error:
        model.complete(MESSAGES)
    text = str(error.value)
    for secret in (API_TOKEN, AIG_TOKEN, CLOUDFLARE_BODY):
        assert secret not in text


def test_failures_without_a_status_have_no_status_code():
    """Un fallo de red no inventa un estado HTTP."""

    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(ModelUnavailable) as error:
        make_model(handler).complete(MESSAGES)
    assert error.value.status_code is None


# --- Registro --------------------------------------------------------------


def test_the_error_log_has_status_and_request_id_but_no_sensitive_data(
    make_cost_client, capsys
):
    """El evento error registra status_code y request_id sin datos sensibles."""
    client = make_cost_client(
        model=FailingModel(401), CF_API_TOKEN=API_TOKEN, CF_AIG_TOKEN=AIG_TOKEN
    )
    response = client.post(
        "/ask",
        json={"question": SECRET_QUESTION},
        headers={"X-Request-ID": REQUEST_ID},
    )
    assert response.status_code == 502
    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    errors = [event for event in events if event["event"] == "error"]
    assert len(errors) == 1
    assert errors[0]["status_code"] == 401
    assert errors[0]["request_id"] == REQUEST_ID
    for secret in (SECRET_QUESTION, CLOUDFLARE_BODY, API_TOKEN, AIG_TOKEN):
        assert secret not in out


def test_the_error_log_reports_a_server_status_too(make_cost_client, capsys):
    """Un fallo 500 del modelo tambien queda registrado con su status_code."""
    client = make_cost_client(model=FailingModel(500))
    client.post("/ask", json={"question": SECRET_QUESTION})
    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    errors = [event for event in events if event["event"] == "error"]
    assert errors[0]["status_code"] == 500
    assert SECRET_QUESTION not in out


def test_the_error_log_includes_the_reason_without_sensitive_data(
    make_cost_client, capsys
):
    """El evento error registra el motivo (mensaje seguro) del fallo."""
    client = make_cost_client(model=FailingModel(503), CF_API_TOKEN=API_TOKEN)
    client.post("/ask", json={"question": SECRET_QUESTION})
    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    errors = [event for event in events if event["event"] == "error"]
    assert errors[0]["reason"]
    for secret in (SECRET_QUESTION, API_TOKEN):
        assert secret not in out
