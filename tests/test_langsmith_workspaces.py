"""Pruebas del diagnóstico de workspaces con transporte simulado, sin red."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "langsmith_workspaces.py"
SECRET = "clave-ficticia-que-no-debe-aparecer"
WORKSPACE = "11111111-1111-1111-1111-111111111111"
ORG = "33333333-3333-3333-3333-333333333333"


@pytest.fixture(name="module")
def module_fixture():
    """Carga el script sin ejecutarlo."""
    spec = importlib.util.spec_from_file_location("workspaces_under_test", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def _transport(status, body=None, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body if body is not None else {})
    return httpx.MockTransport(handler)


def test_lists_names_and_ids_without_requiring_a_workspace_id(module):
    """Sin LANGSMITH_WORKSPACE_ID la consulta funciona y no envía X-Tenant-Id."""
    seen = []
    body = [{"id": WORKSPACE, "display_name": "Workspace 1",
             "organization_id": "22222222-2222-2222-2222-222222222222",
             "is_deleted": False, "is_personal": False, "role_name": "Admin",
             "permissions": ["x"]}]
    report = module.fetch_workspaces({"LANGSMITH_API_KEY": SECRET},
                                     _transport(200, body, seen))
    assert report["passed"] and report["http_status"] == 200
    assert report["workspaces"][0]["display_name"] == "Workspace 1"
    assert "role_name" not in report["workspaces"][0]
    assert "x-tenant-id" not in seen[0].headers
    assert "x-organization-id" not in seen[0].headers
    assert seen[0].url.path == "/api/v1/workspaces"
    assert report["configured_workspace_id_listed"] is None
    assert SECRET not in json.dumps(report)


def test_configured_workspace_is_compared_but_never_sent(module):
    """Si hay LANGSMITH_WORKSPACE_ID se compara con la lista, sin enviarlo."""
    seen = []
    body = [{"id": WORKSPACE, "display_name": "W", "organization_id": None,
             "is_deleted": False, "is_personal": True}]
    env = {"LANGSMITH_API_KEY": SECRET, "LANGSMITH_WORKSPACE_ID": WORKSPACE}
    report = module.fetch_workspaces(env, _transport(200, body, seen))
    assert report["configured_workspace_id_listed"] is True
    assert "x-tenant-id" not in seen[0].headers
    other = module.fetch_workspaces(
        {**env, "LANGSMITH_WORKSPACE_ID": ORG}, _transport(200, body))
    assert other["configured_workspace_id_listed"] is False


def test_organization_id_is_sent_only_when_defined(module):
    """X-Organization-Id solo viaja si el usuario lo define."""
    seen = []
    env = {"LANGSMITH_API_KEY": SECRET, "LANGSMITH_ORGANIZATION_ID": ORG}
    report = module.fetch_workspaces(env, _transport(200, [], seen))
    assert seen[0].headers["x-organization-id"] == ORG
    assert report["header_names_sent"] == ["X-API-Key", "X-Organization-Id"]
    assert ORG not in json.dumps(report)


def test_403_stops_and_separates_confirmed_from_possible_causes(module):
    """Un 403 no se reintenta y se informa sin el cuerpo ni la clave."""
    seen = []
    report = module.fetch_workspaces(
        {"LANGSMITH_API_KEY": SECRET},
        _transport(403, {"detail": f"Forbidden {SECRET}"}, seen))
    assert len(seen) == 1
    assert report["http_status"] == 403 and report["passed"] is False
    assert report["confirmed"] and report["possible_causes_unconfirmed"]
    assert report["workspaces"] == []
    assert SECRET not in json.dumps(report)


def test_connection_errors_are_reported_by_type_only(module):
    """Un fallo de red no incluye mensajes ni encabezados."""
    def broken(_request):
        raise httpx.ConnectError(f"fallo con {SECRET}")

    report = module.fetch_workspaces({"LANGSMITH_API_KEY": SECRET},
                                     httpx.MockTransport(broken))
    assert report["http_status"] is None
    assert report["error_type"] == "ConnectError"
    assert SECRET not in json.dumps(report)


def test_endpoint_suffix_is_normalized(module):
    """Un endpoint con /api/v1 no duplica el prefijo."""
    seen = []
    env = {"LANGSMITH_API_KEY": SECRET,
           "LANGSMITH_ENDPOINT": "https://eu.api.smith.langchain.com/api/v1/"}
    module.fetch_workspaces(env, _transport(200, [], seen))
    assert seen[0].url.path == "/api/v1/workspaces"
    assert seen[0].url.host == "eu.api.smith.langchain.com"


def _status_report(module, status, body, content_type="application/json", **extra):
    seen = []

    def handler(request):
        seen.append(request)
        if body is None:
            return httpx.Response(status, text="<html>error completo</html>",
                                  headers={"content-type": "text/html"})
        return httpx.Response(status, json=body, headers={"content-type": content_type})

    env = {"LANGSMITH_API_KEY": SECRET, **extra}
    return module.fetch_workspaces(env, httpx.MockTransport(handler)), seen


def test_401_extracts_only_a_short_sanitized_code_and_message(module):
    """Del cuerpo solo salen código y mensaje breves, sin la clave ni encabezados."""
    body = {"code": "invalid_api_key",
            "detail": f"Invalid token {SECRET}. X-API-Key: {SECRET} Bearer abc123",
            "debug": {"headers": {"X-API-Key": SECRET}}}
    report, seen = _status_report(module, 401, body)
    assert len(seen) == 1
    assert report["http_status"] == 401
    assert report["error"]["code"] == "invalid_api_key"
    message = report["error"]["message"]
    assert SECRET not in message and "abc123" not in message
    assert "[redacted]" in message
    assert "debug" not in json.dumps(report)
    assert report["confirmed"] and report["possible_causes_unconfirmed"]
    assert SECRET not in json.dumps(report)


def test_error_message_is_length_limited(module):
    """Un mensaje largo se recorta al máximo permitido."""
    report, _ = _status_report(module, 401, {"detail": "x" * 5000})
    assert len(report["error"]["message"]) <= module.MAX_MESSAGE_CHARS


def test_detail_lists_and_non_json_bodies_are_handled(module):
    """Un detalle en lista se resume; un cuerpo no JSON no se guarda."""
    report, _ = _status_report(module, 422, {"detail": [{"msg": "campo faltante"}]})
    assert report["error"]["message"] == "campo faltante"
    assert "confirmed" not in report  # solo 401 y 403 tienen texto de causas
    report, _ = _status_report(module, 502, None)
    assert report["error"]["body_is_json"] is False
    assert "error completo" not in json.dumps(report)


def test_403_text_does_not_claim_independence_from_the_workspace_id(module):
    """La ausencia del encabezado no se presenta como prueba sobre el workspace."""
    report, _ = _status_report(module, 403, {"detail": "Forbidden"})
    text = json.dumps(report, ensure_ascii=False)
    assert "no depende" not in text
    assert "no permite concluir" in text


@pytest.mark.parametrize("env,name,problem", [
    ({"LANGSMITH_API_KEY": '"abc123"'}, "LANGSMITH_API_KEY", "comillas"),
    ({"LANGSMITH_API_KEY": "abc123 "}, "LANGSMITH_API_KEY",
     "espacios_en_los_extremos"),
    ({"LANGSMITH_API_KEY": "abc 123"}, "LANGSMITH_API_KEY", "espacios_internos"),
    ({"LANGSMITH_ENDPOINT": "'https://api.smith.langchain.com'"},
     "LANGSMITH_ENDPOINT", "comillas"),
    ({"LANGSMITH_ENDPOINT": "http://api.smith.langchain.com"},
     "LANGSMITH_ENDPOINT", "no_es_url_https"),
    ({"LANGSMITH_ORGANIZATION_ID": "no-es-uuid"},
     "LANGSMITH_ORGANIZATION_ID", "no_es_uuid"),
    ({"LANGSMITH_ORGANIZATION_ID": f" {ORG}"},
     "LANGSMITH_ORGANIZATION_ID", "espacios_en_los_extremos"),
])
def test_invalid_local_format_sends_no_request_and_shows_no_value(
        module, env, name, problem):
    """Un formato inválido se informa por categoría y no se envía la petición."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[])

    full = {"LANGSMITH_API_KEY": SECRET, **env}
    report = module.fetch_workspaces(full, httpx.MockTransport(handler))
    assert not seen
    assert report["request_sent"] is False and report["passed"] is False
    assert report["local_validation"][name]["estado"] == "inválido"
    assert problem in report["local_validation"][name]["problemas"]
    dump = json.dumps(report)
    assert SECRET not in dump and ORG not in dump
    assert "abc123" not in dump


def test_valid_inputs_are_marked_valid_and_the_request_is_sent(module):
    """Con valores válidos se informa 'válido' y se hace la consulta."""
    env = {"LANGSMITH_API_KEY": SECRET, "LANGSMITH_ORGANIZATION_ID": ORG,
           "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com"}
    report = module.fetch_workspaces(env, _transport(200, []))
    checks = report["local_validation"]
    assert checks["LANGSMITH_API_KEY"] == {"estado": "válido"}
    assert checks["LANGSMITH_ORGANIZATION_ID"] == {"estado": "válido"}
    assert checks["LANGSMITH_WORKSPACE_ID"] == {"estado": "no definido"}
    assert report["request_sent"] is True
    assert report["header_names_sent"] == ["X-API-Key", "X-Organization-Id"]
