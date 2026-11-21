"""Pruebas del chequeo de acceso a LangSmith con un cliente simulado, sin red."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test",
                                                  SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Forbidden(Exception):
    """Error con código HTTP, como los de la biblioteca de LangSmith."""

    def __init__(self, status):
        super().__init__(f"Failed to ... {status} Forbidden for url ...")
        self.response = type("Response", (), {"status_code": status})()


class FakeClient:  # pylint: disable=too-many-instance-attributes
    """Cliente de LangSmith simulado con fallos configurables."""

    def __init__(self, fail_list=None, fail_project=None, visible=True):
        self.fail_list = fail_list
        self.fail_project = fail_project
        self.visible = visible
        self.created = []
        self.updated = []
        self.flushed = 0

    def list_projects(self, limit=1):
        """Lista proyectos o falla."""
        if self.fail_list:
            raise self.fail_list
        return iter([object()][:limit])

    def read_project(self, project_name):
        """Lee un proyecto o falla."""
        if self.fail_project:
            raise self.fail_project
        return project_name

    def create_run(self, **kwargs):
        """Registra la traza enviada."""
        self.created.append(kwargs)

    def update_run(self, run_id, **kwargs):
        """Registra el cierre de la traza."""
        self.updated.append((run_id, kwargs))

    def flush(self):
        """Cuenta los vaciados de la cola."""
        self.flushed += 1

    def list_runs(self, **_kwargs):
        """Devuelve la traza solo si es visible."""
        return iter([object()] if self.visible else [])


@pytest.fixture(name="check")
def check_fixture():
    """Módulo del chequeo cargado sin ejecutarlo."""
    return _load("langsmith_check")


def _run(check, client, **kwargs):
    return check.check_access(client, "proyecto", wait_seconds=0,
                              sleep=lambda _s: None, **kwargs)


def test_full_access_passes_and_sends_only_hidden_content(check):
    """Con acceso completo pasa; la traza de prueba no lleva contenido real."""
    client = FakeClient()
    report = _run(check, client)
    assert report["passed"] is True
    assert all(step["ok"] for step in report["steps"].values())
    sent = client.created[0]
    assert sent["inputs"] == {"data": "[hidden]"}
    assert client.updated[0][1]["outputs"] == {"data": "[hidden]"}
    assert client.flushed == 1


def test_read_forbidden_is_reported_with_the_http_status(check):
    """Un 403 al leer se informa por paso, con tipo y código, sin el mensaje."""
    report = _run(check, FakeClient(fail_list=Forbidden(403),
                                    fail_project=Forbidden(403)))
    assert report["passed"] is False
    assert report["steps"]["read_access"] == {
        "ok": False, "error_type": "Forbidden", "http_status": 403}
    assert report["steps"]["read_project"]["http_status"] == 403
    assert "Forbidden for url" not in json.dumps(report)


def test_missing_project_is_not_a_failure(check):
    """Un 404 al leer el proyecto es aceptable: se crea en la primera escritura."""
    report = _run(check, FakeClient(fail_project=Forbidden(404)))
    assert report["steps"]["read_project"] == {"ok": True, "project_exists": False}
    assert report["passed"] is True


def test_a_write_that_never_appears_fails(check):
    """Si la traza enviada no se puede leer de vuelta, la escritura no se acepta."""
    report = _run(check, FakeClient(visible=False))
    assert report["steps"]["write_access"]["ok"] is False
    assert report["passed"] is False


def test_read_only_sends_no_trace(check):
    """--read-only no crea trazas."""
    client = FakeClient()
    report = _run(check, client, read_only=True)
    assert report["passed"] is True
    assert "write_access" not in report["steps"]
    assert not client.created


def test_environment_report_never_contains_values(check, monkeypatch):
    """Solo informa definida o vacía."""
    monkeypatch.setenv("LANGSMITH_API_KEY", "valor-secreto-ficticio")
    monkeypatch.delenv("LANGSMITH_WORKSPACE_ID", raising=False)
    report = check.environment_report()
    assert report["LANGSMITH_API_KEY"] == "definida"
    assert report["LANGSMITH_WORKSPACE_ID"] == "vacía"
    assert "valor-secreto-ficticio" not in json.dumps(report)
