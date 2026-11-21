"""Pruebas del chequeo del catálogo de Cloudflare con transporte simulado, sin red."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cf_models_check.py"
ACCOUNT = "a" * 32
TOKEN = "token-ficticio-que-no-debe-aparecer"
ENV = {"CF_ACCOUNT_ID": ACCOUNT, "CF_API_TOKEN": TOKEN}


@pytest.fixture(name="module")
def module_fixture():
    """Carga el script sin ejecutarlo."""
    spec = importlib.util.spec_from_file_location("cf_check_under_test", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def _catalog(names):
    return {"success": True, "result": [
        {"name": name, "task": {"name": "Text Generation"},
         "properties": [{"property_id": "price", "value": [{"unit": "x"}]},
                        {"property_id": "beta", "value": True}]}
        for name in names]}


def test_reports_which_candidates_are_listed_and_never_runs_a_model(module):
    """Marca cada candidato como listado o no y solo hace GET al catálogo."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_catalog(
            ["@cf/meta/llama-3.3-70b-instruct-fp8-fast",
             "@cf/meta/llama-3.1-8b-instruct-fast"]))

    report = module.check_models(ENV, httpx.MockTransport(handler))
    assert report["passed"] is True
    assert {request.method for request in seen} == {"GET"}
    assert all("/ai/models/search" in request.url.path for request in seen)
    assert len(seen) == 2
    cands = report["candidates"]
    assert cands["@cf/meta/llama-3.1-8b-instruct-fast"]["listed"] is True
    assert cands["@cf/meta/llama-3.1-8b-instruct-fp8-fast"] == {"listed": False}
    assert "beta" not in json.dumps(report)  # solo price y context_window
    assert TOKEN not in json.dumps(report)


def test_http_errors_show_status_and_sanitized_message_only(module):
    """Un 403 se detiene tras la primera consulta, sin token ni cuerpo completo."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(403, json={
            "errors": [{"message": f"denied {TOKEN}"}],
            "detail": f"Authorization: Bearer {TOKEN} extra", "code": "forbidden"})

    report = module.check_models(ENV, httpx.MockTransport(handler))
    assert len(seen) == 1
    assert report["queries"][0]["http_status"] == 403
    assert report["queries"][0]["error"]["code"] == "forbidden"
    assert report["passed"] is False
    assert TOKEN not in json.dumps(report)
    assert "errors" not in json.dumps(report)


@pytest.mark.parametrize("env", [
    {"CF_API_TOKEN": TOKEN},
    {"CF_ACCOUNT_ID": "corta", "CF_API_TOKEN": TOKEN},
    {"CF_ACCOUNT_ID": ACCOUNT, "CF_API_TOKEN": f'"{TOKEN}"'},
    {"CF_ACCOUNT_ID": ACCOUNT, "CF_API_TOKEN": TOKEN + " "},
])
def test_invalid_local_values_send_nothing(module, env):
    """Con valores ausentes o mal formados no se envía ninguna petición."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={})

    report = module.check_models(env, httpx.MockTransport(handler))
    assert not seen
    assert report["stage"] == "local_validation_failed"
    assert TOKEN not in json.dumps(report)


def _model(name, inp, out, **extra):
    props = [{"property_id": "price", "value": [
        {"unit": "per M input tokens", "price": inp, "currency": "USD"},
        {"unit": "per M output tokens", "price": out, "currency": "USD"}]},
        {"property_id": "context_window", "value": "24000"}]
    props += [{"property_id": key, "value": value} for key, value in extra.items()]
    return {"name": name, "task": {"name": "Text Generation"}, "properties": props}


def test_scan_follows_pages_and_ranks_by_cost(module, monkeypatch):
    """Recorre varias páginas, filtra por tarea y ordena por costo ponderado."""
    monkeypatch.setattr(module, "SCAN_PER_PAGE", 2)
    pages = {1: [_model("@cf/a/caro", 1.0, 3.0), _model("@cf/a/medio", 0.3, 1.0)],
             2: [_model("@cf/a/barato", 0.05, 0.3, beta=True)]}
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"success": True, "result": pages[page]})

    report = module.scan_text_generation(ENV, httpx.MockTransport(handler))
    assert report["passed"] is True and report["total_models"] == 3
    assert [row["name"] for row in report["models"]] == [
        "@cf/a/barato", "@cf/a/medio", "@cf/a/caro"]
    assert report["models"][0]["price_usd_per_million"] == {"input": 0.05,
                                                            "output": 0.3}
    assert report["models"][0]["beta"] == "True"
    assert [item["page"] for item in seen] == ["1", "2"]
    assert all(item["task"] == "Text Generation" for item in seen)
    assert TOKEN not in json.dumps(report)


def test_scan_detects_an_ignored_page_parameter(module):
    """Si la página 2 repite la 1, se detiene y lo informa, sin bucle."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"result": [_model("@cf/a/x", 1, 2)] * 50})

    report = module.scan_text_generation(ENV, httpx.MockTransport(handler))
    assert report["pagination_ignored_or_finished"] is True
    assert len(seen) == 2


def test_scan_page_cap_and_errors_stop_safely(module, monkeypatch):
    """El tope de páginas se informa; un 403 detiene el recorrido."""
    monkeypatch.setattr(module, "SCAN_MAX_PAGES", 2)
    monkeypatch.setattr(module, "SCAN_PER_PAGE", 1)
    counter = iter(range(100))

    def endless(_request):
        return httpx.Response(200, json={"result": [_model(f"@cf/a/{next(counter)}",
                                                           1, 2)]})

    capped = module.scan_text_generation(ENV, httpx.MockTransport(endless))
    assert capped["page_cap_reached"] is True and len(capped["pages"]) == 2

    seen = []

    def denied(request):
        seen.append(request)
        return httpx.Response(403, json={"detail": f"no {TOKEN}"})

    report = module.scan_text_generation(ENV, httpx.MockTransport(denied))
    assert len(seen) == 1 and report["passed"] is False
    assert TOKEN not in json.dumps(report)


def test_models_without_a_parseable_price_are_listed_last(module):
    """Sin precio interpretable no se asume ninguno; se cuenta aparte."""
    def handler(_request):
        return httpx.Response(200, json={"result": [
            {"name": "@cf/a/sin-precio", "properties": []},
            _model("@cf/a/con-precio", 1, 2)]})

    report = module.scan_text_generation(ENV, httpx.MockTransport(handler))
    assert report["models"][-1]["name"] == "@cf/a/sin-precio"
    assert report["models"][-1]["price_usd_per_million"] is None
    assert report["without_parseable_price"] == 1
