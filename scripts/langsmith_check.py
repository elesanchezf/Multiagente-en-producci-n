"""Chequeo independiente de acceso a LangSmith. No invoca Cloudflare ni ningún modelo.

Pasos (cada uno se informa por separado):
  1. read_access   lista un proyecto: valida clave, endpoint y espacio de trabajo.
  2. read_project  busca el proyecto configurado; si no existe se crea al escribir.
  3. write_access  envía UNA traza mínima con entradas y salidas ocultas y la lee de
                   vuelta por su metadato; confirma permiso de escritura y lectura.
Con --read-only se omite el paso 3 (no envía trazas).

Lee solo variables de entorno (LANGSMITH_API_KEY, LANGSMITH_ENDPOINT,
LANGSMITH_WORKSPACE_ID, LANGSMITH_PROJECT); no imprime ni guarda sus valores.
El informe va a evidence/langsmith-check/ y el código de salida es 0 solo si todo pasa.
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_PROJECT = "default"  # el mismo que usa la aplicación sin LANGSMITH_PROJECT
HIDDEN = {"data": "[hidden]"}
STATUS_PATTERN = re.compile(r"\b([45]\d\d)\b")


def describe_error(error):
    """Tipo y código HTTP de un error, sin mensaje (puede incluir rutas o nombres)."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status is None:
        match = STATUS_PATTERN.search(str(error))
        status = int(match.group(1)) if match else None
    return {"error_type": type(error).__name__, "http_status": status}


def _step(report, name, action):
    """Ejecuta un paso; registra éxito o el error descrito, nunca lanza."""
    try:
        detail = action() or {}
        report["steps"][name] = {"ok": True, **detail}
        return True
    except Exception as error:  # pylint: disable=broad-exception-caught
        report["steps"][name] = {"ok": False, **describe_error(error)}
        return False


def _read_project(client, project):
    """Un 404 es aceptable: LangSmith crea el proyecto en la primera escritura."""
    try:
        client.read_project(project_name=project)
        return {"project_exists": True}
    except Exception as error:  # pylint: disable=broad-exception-caught
        if describe_error(error)["http_status"] == 404 or type(
                error).__name__ == "LangSmithNotFoundError":
            return {"project_exists": False}
        raise


def _write_and_read_back(client, project, wait_seconds, sleep):
    """Envía una traza oculta y la busca por su metadato; falla si no aparece."""
    marker = f"lscheck-{uuid.uuid4().hex[:12]}"
    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    client.create_run(
        name="access_check", run_type="chain", id=run_id, project_name=project,
        inputs=HIDDEN, start_time=now,
        extra={"metadata": {"request_id": marker, "purpose": "access_check"}})
    client.update_run(run_id, outputs=HIDDEN, end_time=datetime.now(timezone.utc))
    client.flush()
    query = ('and(eq(metadata_key, "request_id"), '
             f'eq(metadata_value, "{marker}"))')
    deadline = time.time() + wait_seconds
    while True:
        if any(True for _ in client.list_runs(project_name=project, filter=query)):
            return {"marker": marker, "readback": True}
        if time.time() >= deadline:
            raise LookupError("trace not visible after write: ingest rejected or late")
        sleep(3)


def check_access(client, project, read_only=False, wait_seconds=45, sleep=time.sleep):
    """Ejecuta el chequeo con el cliente dado; devuelve el informe."""
    report = {"project": project, "read_only": read_only, "steps": {}}
    ok = _step(report, "read_access",
               lambda: next(iter(client.list_projects(limit=1)), None) and {})
    ok = _step(report, "read_project", lambda: _read_project(client, project)) and ok
    if not read_only:
        ok = _step(report, "write_access", lambda: _write_and_read_back(
            client, project, wait_seconds, sleep)) and ok
    report["passed"] = ok
    return report


def environment_report():
    """Presencia (nunca valores) de las variables que usa LangSmith."""
    names = ("LANGSMITH_API_KEY", "LANGSMITH_ENDPOINT", "LANGSMITH_WORKSPACE_ID",
             "LANGSMITH_PROJECT")
    return {name: ("definida" if os.environ.get(name) else "vacía") for name in names}


def save_report(report):
    """Guarda el informe y devuelve su ruta relativa."""
    folder = ROOT / "evidence" / "langsmith-check"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = folder / f"{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.relative_to(ROOT)


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--read-only", action="store_true",
                        help="no envía ninguna traza")
    args = parser.parse_args()
    variables = environment_report()
    if variables["LANGSMITH_API_KEY"] != "definida":
        print("Falta LANGSMITH_API_KEY.", json.dumps(variables, ensure_ascii=False))
        return 2
    project = os.environ.get("LANGSMITH_PROJECT") or DEFAULT_PROJECT
    try:
        from langsmith import Client  # pylint: disable=import-outside-toplevel
        client = Client()
    except Exception as error:  # pylint: disable=broad-exception-caught
        report = {"project": project, "passed": False, "steps": {
            "client": {"ok": False, **describe_error(error)}}}
    else:
        report = check_access(client, project, read_only=args.read_only)
    report["variables"] = variables
    report["date_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = save_report(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Informe:", path)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
