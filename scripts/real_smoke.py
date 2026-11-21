"""Prueba pequeña: una consulta completa con el mismo request_id en todo.

Verifica que coordinador, directorio y revisor se ejecutan y que el
``request_id`` coincide en: encabezado y cuerpo de la respuesta, eventos del log
JSON y metadatos de las trazas de LangSmith.

Modos:
  (sin banderas)         lista qué variables existen (solo "definida"/"vacía")
                         y las llamadas máximas; sin red.
  --provider fake        comprueba respuesta y log localmente; sin red.
  --provider gateway --confirm-real-calls
                         una sola solicitud real (máximo 4 llamadas al modelo)
                         y, si LANGSMITH_* está definido, consulta de la traza.
Lee solo variables de entorno (nunca .env). No imprime secretos ni contenido de
preguntas o respuestas.
"""

import argparse
import contextlib
import io
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# pylint: disable=wrong-import-position
from fastapi.testclient import TestClient  # noqa: E402

import app.main as app_main  # noqa: E402
from scripts import langsmith_check  # noqa: E402
from app.budget import BudgetGuard, wrap_models  # noqa: E402
from app.config import load_config  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pricing import Pricing  # noqa: E402

QUESTION = "EMP-0001"  # dato ficticio
MAX_MODEL_CALLS = 4  # AGENT_MAX_STEPS (3) + una revisión
MAX_USD = 0.01  # presupuesto estimado (no un máximo garantizado de gasto)
MAX_INPUT_TOKENS = 3000  # tope de la estimación de entrada por llamada
SMOKE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"  # precio confirmado
EXPECTED_ID = "EMP-0001"
EXPECTED_NAME = "Ana López"
EXPECTED_EVENTS = {"handoff", "agent_run", "workflow_completed", "request"}
EXPECTED_RUNS = {"coordinator", "directory_agent", "agent_run", "model_call",
                 "reviewer_agent", "reviewer_model_call"}
VARIABLES = {
    "gateway": ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN", "CF_AIG_TOKEN"),
    "langsmith": ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT",
                  "LANGSMITH_ENDPOINT", "LANGSMITH_WORKSPACE_ID",
                  "HIDE_INPUTS", "HIDE_OUTPUTS"),
}
# Solo se heredan credenciales y destino; el modelo y los límites son explícitos.
PASSTHROUGH = tuple(name for names in VARIABLES.values() for name in names)


def presence_report():
    """Indica si cada variable está definida, sin mostrar su valor."""
    return {name: ("definida" if os.environ.get(name) else "vacía")
            for names in VARIABLES.values() for name in names}


def log_events(text, request_id):
    """Nombres de evento del log JSON que llevan el request_id dado."""
    events = []
    for line in text.splitlines():
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if data.get("request_id") == request_id:
                events.append(data.get("event"))
    return events


def langsmith_runs(request_id, project, wait_seconds=60):
    """Nombres de las trazas con ese request_id en los metadatos (solo lectura)."""
    # pylint: disable=import-outside-toplevel
    from langsmith import Client
    client = Client()
    client.flush()
    query = ('and(eq(metadata_key, "request_id"), '
             f'eq(metadata_value, "{request_id}"))')
    deadline = time.time() + wait_seconds
    names = []
    while time.time() < deadline:
        names = [run.name for run in client.list_runs(
            project_name=project, filter=query)]
        if EXPECTED_RUNS <= set(names):
            break
        time.sleep(5)
    return names


def build_env(provider, check_traces, api_key):
    """Entorno de la prueba: modelo, pasos y salida fijados, sin herencia."""
    env = {"MODEL_PROVIDER": provider, "ENVIRONMENT": "development",
           "API_KEYS": f"smoke:{api_key}", "RATE_LIMIT_PER_MINUTE": "100",
           "MODEL_SMALL": SMOKE_MODEL, "MODEL_LARGE": SMOKE_MODEL,
           "AGENT_MAX_STEPS": "3", "MODEL_MAX_TOKENS": "300",
           "MODEL_TEMPERATURE": "0",
           "EMPLOYEES_PATH": str(ROOT / "data" / "employees.json"),
           "PRICES_PATH": str(ROOT / "data" / "model_prices.json"),
           "LANGSMITH_TRACING": "true" if check_traces else "false",
           "HIDE_INPUTS": "true", "HIDE_OUTPUTS": "true",
           "ROUTING": "false", "CACHE_TTL_SECONDS": "0"}
    for name in PASSTHROUGH:
        if os.environ.get(name) and name not in env:
            env[name] = os.environ[name]
    return env


def employee_names():
    """Nombres del directorio ficticio, para detectar respuestas de otro empleado."""
    path = ROOT / "data" / "employees.json"
    return {item["id"]: item["name"]
            for item in json.loads(path.read_text(encoding="utf-8"))}


def answer_matches(answer):
    """La respuesta describe al empleado consultado y a ningún otro."""
    text = answer or ""
    others = [name for key, name in employee_names().items() if key != EXPECTED_ID]
    return (EXPECTED_ID in text and EXPECTED_NAME in text
            and not any(name in text for name in others))


def smoke_passed(report, needs_traces):
    """Criterio único de aprobación; cualquier condición faltante la deniega."""
    traces = report.get("langsmith_complete")
    return bool(
        report.get("hide_inputs") is True and report.get("hide_outputs") is True
        and report.get("status") == 200
        and report.get("header_matches") is True
        and report.get("body_matches") is True
        and report.get("log_events_complete") is True
        and report.get("agents_used") == ["coordinator", "directory", "reviewer"]
        and report.get("review_status") == "approved"
        and report.get("model") == SMOKE_MODEL
        and report.get("model_calls", MAX_MODEL_CALLS + 1) <= MAX_MODEL_CALLS
        and report.get("answer_matches_employee") is True
        and (traces is True or (traces is None and not needs_traces)))


def _send(provider, check_traces, request_id):
    """Envía una solicitud con límites; devuelve configuración, guardián y datos."""
    api_key = secrets.token_urlsafe(24)
    config = load_config(build_env(provider, check_traces, api_key))
    guard = BudgetGuard(Pricing.from_file(config.prices_path), MAX_MODEL_CALLS,
                        MAX_USD, MAX_INPUT_TOKENS, config.model_max_tokens)
    real_build = app_main.build_models
    app_main.build_models = lambda cfg, directory: wrap_models(
        real_build(cfg, directory), guard)
    try:
        client = TestClient(create_app(config=config),
                            raise_server_exceptions=False)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            response = client.post("/ask", json={"question": QUESTION}, headers={
                "X-API-Key": api_key, "X-Request-ID": request_id})
    finally:
        app_main.build_models = real_build
    return config, guard, response, captured.getvalue()


def _tokens(body):
    """Consumo por agente: directorio = total menos revisor."""
    total_in, total_out = body.get("input_tokens") or 0, body.get(
        "output_tokens") or 0
    rev_in, rev_out = body.get("review_input_tokens") or 0, body.get(
        "review_output_tokens") or 0
    return {"total_input": total_in, "total_output": total_out,
            "reviewer_input": rev_in, "reviewer_output": rev_out,
            "directory_input": total_in - rev_in,
            "directory_output": total_out - rev_out}


def run_smoke(provider, check_traces, save=None):
    """Ejecuta una solicitud y devuelve el informe (datos ficticios, sin secretos).

    :param save: Función que persiste el informe. Se llama con un informe parcial
        justo después de la consulta al modelo (antes de tocar LangSmith) y de nuevo
        al terminar, de modo que un fallo de LangSmith no pierda el consumo medido.
    """
    request_id = f"smoke-{uuid.uuid4().hex[:12]}"
    config, guard, response, log_text = _send(provider, check_traces, request_id)
    body = response.json() if response.status_code == 200 else {}
    events = set(log_events(log_text, request_id))
    report = {
        "provider": provider, "request_id": request_id,
        "status": response.status_code,
        "header_matches": response.headers.get("X-Request-ID") == request_id,
        "body_matches": body.get("request_id") == request_id,
        "agents_used": body.get("agents_used"),
        "review_status": body.get("review_status"),
        "model_calls": body.get("steps", 0) + body.get("review_calls", 0),
        "hide_inputs": config.hide_inputs, "hide_outputs": config.hide_outputs,
        "model": body.get("model"), "route": body.get("route"),
        "answer": body.get("answer"),
        "answer_matches_employee": answer_matches(body.get("answer")),
        "tokens": _tokens(body),
        "cost_usd_estimated": body.get("cost_usd"),
        "reviewer_cost_usd_estimated": body.get("review_cost_usd"),
        "budget": {"calls_made": guard.calls, "max_calls": guard.max_calls,
                   "spent_usd_from_usage": round(guard.spent_usd, 8),
                   "max_usd": guard.max_usd, "tripped": guard.tripped,
                   "per_call": guard.usage},
        "log_events_found": sorted(events),
        "log_events_complete": EXPECTED_EVENTS <= events,
        "langsmith_complete": None,  # no verificado
    }
    report.update(stage="model_done", passed=False)
    if save:
        save(report)
    if check_traces:
        project = os.environ.get("LANGSMITH_PROJECT") or "default"
        report["langsmith_project"] = project
        try:
            names = set(langsmith_runs(request_id, project))
            report.update(langsmith_runs_found=sorted(names),
                          langsmith_complete=EXPECTED_RUNS <= names)
        except Exception as error:  # pylint: disable=broad-exception-caught
            report.update(langsmith_complete=False,
                          langsmith_error=langsmith_check.describe_error(error))
    report["passed"] = smoke_passed(report, provider == "gateway")
    report["stage"] = "complete"
    if save:
        save(report)
    return report


def langsmith_preflight():
    """Chequeo de acceso a LangSmith previo a cualquier llamada al modelo."""
    project = os.environ.get("LANGSMITH_PROJECT") or "default"
    try:
        from langsmith import Client  # pylint: disable=import-outside-toplevel
        return langsmith_check.check_access(Client(), project)
    except Exception as error:  # pylint: disable=broad-exception-caught
        return {"project": project, "passed": False, "steps": {
            "client": {"ok": False, **langsmith_check.describe_error(error)}}}


def _writer(provider):
    """Devuelve la función que guarda el informe (el mismo archivo cada vez)."""
    folder = ROOT / "evidence" / "smoke-real"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = folder / f"{provider}-{stamp}.json"

    def save(report):
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return save


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=("fake", "gateway"))
    parser.add_argument("--confirm-real-calls", action="store_true")
    args = parser.parse_args()
    if args.provider is None:
        print(json.dumps({"variables": presence_report(),
                          "max_model_calls": MAX_MODEL_CALLS}, indent=2,
                         ensure_ascii=False))
        return 0
    traces = False
    if args.provider == "gateway":
        if not args.confirm_real_calls:
            print("Use --confirm-real-calls para autorizar hasta "
                  f"{MAX_MODEL_CALLS} llamadas reales.")
            return 2
        missing = [n for n in ("CF_ACCOUNT_ID", "CF_API_TOKEN")
                   if not os.environ.get(n)]
        if missing:
            print("Faltan variables de entorno:", ", ".join(missing))
            return 2
        if not os.environ.get("LANGSMITH_API_KEY"):
            print("Falta LANGSMITH_API_KEY: la correlación en LangSmith es parte "
                  "de la prueba.")
            return 2
        traces = True
        access = langsmith_preflight()
        if not access["passed"]:
            access["variables"] = langsmith_check.environment_report()
            langsmith_check.save_report(access)
            print("LangSmith no está accesible; no se hizo ninguna llamada al modelo.")
            print(json.dumps(access, indent=2, ensure_ascii=False))
            return 2
    save = _writer(args.provider)
    try:
        report = run_smoke(args.provider, traces, save)
    except Exception as error:  # pylint: disable=broad-exception-caught
        report = {"stage": "failed", "passed": False,
                  "error": langsmith_check.describe_error(error)}
        save(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
