"""Pruebas del criterio de aprobación de scripts/real_smoke.py, sin red."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.llm import FakeModel, ModelResponse

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "real_smoke.py"


@pytest.fixture(name="smoke")
def smoke_fixture():
    """Carga el script como módulo sin ejecutarlo."""
    spec = importlib.util.spec_from_file_location("real_smoke_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _good_report(smoke):
    return {
        "hide_inputs": True, "hide_outputs": True, "status": 200,
        "header_matches": True, "body_matches": True, "log_events_complete": True,
        "agents_used": ["coordinator", "directory", "reviewer"],
        "review_status": "approved", "model": smoke.SMOKE_MODEL, "model_calls": 3,
        "answer_matches_employee": True, "langsmith_complete": True,
    }


def test_a_complete_report_passes(smoke):
    """Con todas las condiciones, incluida LangSmith, la prueba se aprueba."""
    assert smoke.smoke_passed(_good_report(smoke), needs_traces=True)


@pytest.mark.parametrize("field,value", [
    ("review_status", "rejected"),
    ("review_status", "skipped_incomplete"),
    ("review_status", "no_evidence"),
    ("answer_matches_employee", False),
    ("model", "@cf/meta/llama-3.1-8b-instruct-fast"),
    ("model_calls", 5),
    ("hide_inputs", False),
    ("hide_outputs", False),
    ("langsmith_complete", False),
    ("langsmith_complete", None),
    ("log_events_complete", False),
])
def test_any_missing_condition_denies_the_smoke(smoke, field, value):
    """Rechazo del revisor, otro empleado, otro modelo o falta de trazas no pasan."""
    report = _good_report(smoke)
    report[field] = value
    assert not smoke.smoke_passed(report, needs_traces=True)


def test_the_answer_must_describe_only_the_requested_employee(smoke):
    """Una respuesta de otro empleado o mezclada no corresponde a EMP-0001."""
    assert smoke.answer_matches("id: EMP-0001; name: Ana López; status: activo")
    assert not smoke.answer_matches("id: EMP-0002; name: Luis Pérez")
    assert not smoke.answer_matches("EMP-0001 Ana López y Luis Pérez")
    assert not smoke.answer_matches(None)


def test_a_reviewer_rejection_does_not_pass_end_to_end(smoke, monkeypatch):
    """Ejecución completa con un revisor que rechaza: passed es falso."""
    class RejectingReviewer:  # pylint: disable=too-few-public-methods
        """Modelo simulado cuyo revisor siempre rechaza."""

        def __init__(self, directory):
            self._inner = FakeModel(directory, smoke.SMOKE_MODEL)

        def complete(self, messages):
            """Rechaza en la revisión y delega el resto."""
            if messages[0]["content"].startswith("Eres un revisor"):
                return ModelResponse('{"approved":false}', 1, 1)
            return self._inner.complete(messages)

    monkeypatch.setattr(
        smoke.app_main, "build_models",
        lambda _config, directory: {smoke.SMOKE_MODEL: RejectingReviewer(directory)},
    )
    report = smoke.run_smoke("fake", check_traces=False)
    assert report["review_status"] == "rejected"
    assert report["passed"] is False
    assert report["budget"]["calls_made"] <= smoke.MAX_MODEL_CALLS


def test_an_approved_fake_run_passes_locally(smoke):
    """Control positivo: el modelo simulado aprobado pasa la prueba local."""
    report = smoke.run_smoke("fake", check_traces=False)
    assert report["review_status"] == "approved"
    assert report["answer_matches_employee"] is True
    assert report["passed"] is True


def test_model_and_limits_are_explicit_not_inherited(smoke, monkeypatch):
    """Variables heredadas no cambian el modelo de 70B, los pasos ni la salida."""
    monkeypatch.setenv("MODEL_SMALL", "@cf/meta/llama-3.1-8b-instruct-fast")
    monkeypatch.setenv("MODEL_LARGE", "otro/modelo")
    monkeypatch.setenv("AGENT_MAX_STEPS", "9")
    monkeypatch.setenv("MODEL_MAX_TOKENS", "4000")
    monkeypatch.setenv("ROUTING", "true")
    env = smoke.build_env("gateway", True, "clave-de-prueba-0000")
    assert env["MODEL_SMALL"] == env["MODEL_LARGE"] == smoke.SMOKE_MODEL
    assert env["AGENT_MAX_STEPS"] == "3"
    assert env["MODEL_MAX_TOKENS"] == "300"
    assert env["ROUTING"] == "false"
    assert env["HIDE_INPUTS"] == env["HIDE_OUTPUTS"] == "true"
    assert smoke.MAX_MODEL_CALLS == 4


def _http_error(status):
    error = RuntimeError(f"{status} Forbidden")
    error.response = type("Response", (), {"status_code": status})()
    return error


def test_a_langsmith_failure_still_saves_the_partial_report(smoke, monkeypatch):
    """Un 403 de LangSmith no pierde el consumo del modelo ya medido."""
    saved = []

    def forbidden(*_args, **_kwargs):
        raise _http_error(403)

    monkeypatch.setattr(smoke, "langsmith_runs", forbidden)
    report = smoke.run_smoke("fake", check_traces=True,
                             save=lambda item: saved.append(dict(item)))
    assert [item["stage"] for item in saved] == ["model_done", "complete"]
    assert saved[0]["tokens"]["total_input"] > 0  # consumo guardado antes de LangSmith
    assert saved[0]["passed"] is False
    assert report["langsmith_complete"] is False
    assert report["langsmith_error"]["http_status"] == 403
    assert report["passed"] is False


def test_main_writes_the_report_file_when_langsmith_fails(smoke, monkeypatch, tmp_path):
    """La ejecución real deja el archivo del informe aunque LangSmith falle."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("403 Forbidden")

    data = tmp_path / "data"
    data.mkdir()
    for name in ("employees.json", "model_prices.json"):
        (data / name).write_bytes((smoke.ROOT / "data" / name).read_bytes())
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "langsmith_runs", boom)
    monkeypatch.setattr(smoke, "langsmith_preflight", lambda: {"passed": True})
    monkeypatch.setenv("CF_ACCOUNT_ID", "cuenta-ficticia")
    monkeypatch.setenv("CF_API_TOKEN", "token-ficticio")
    monkeypatch.setenv("LANGSMITH_API_KEY", "clave-ficticia")
    # El proveedor real se sustituye por el simulado: sin red.
    monkeypatch.setattr(smoke.app_main, "build_models", lambda _c, directory: {
        smoke.SMOKE_MODEL: FakeModel(directory, smoke.SMOKE_MODEL)})
    monkeypatch.setattr("sys.argv", ["real_smoke.py", "--provider", "gateway",
                                     "--confirm-real-calls"])
    assert smoke.main() == 1
    files = list((tmp_path / "evidence" / "smoke-real").glob("gateway-*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["stage"] == "complete"
    assert data["langsmith_error"]["http_status"] == 403
    assert data["tokens"]["total_input"] > 0
    assert "clave-ficticia" not in files[0].read_text(encoding="utf-8")


def test_failed_preflight_makes_no_model_call(smoke, monkeypatch, tmp_path):
    """Sin acceso a LangSmith la prueba real se detiene antes de llamar al modelo."""
    monkeypatch.setattr(smoke.langsmith_check, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "langsmith_preflight", lambda: {
        "passed": False, "steps": {"read_access": {"ok": False, "http_status": 403}}})

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("El modelo no debe invocarse")

    monkeypatch.setattr(smoke, "run_smoke", must_not_run)
    monkeypatch.setenv("CF_ACCOUNT_ID", "cuenta-ficticia")
    monkeypatch.setenv("CF_API_TOKEN", "token-ficticio")
    monkeypatch.setenv("LANGSMITH_API_KEY", "clave-ficticia")
    monkeypatch.setattr("sys.argv", ["real_smoke.py", "--provider", "gateway",
                                     "--confirm-real-calls"])
    assert smoke.main() == 2
