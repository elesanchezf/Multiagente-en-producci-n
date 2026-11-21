"""Diagnóstico de solo lectura: workspaces de LangSmith accesibles con la clave.

Primero valida localmente el formato de la clave, el endpoint y los identificadores
(solo válido/inválido; si algo es inválido NO se envía la petición). Después hace una
única petición ``GET /api/v1/workspaces`` sin reintentos. No exige
``LANGSMITH_WORKSPACE_ID`` y no envía ``X-Tenant-Id``; solo envía
``X-Organization-Id`` si ``LANGSMITH_ORGANIZATION_ID`` está definido y es válido.
No invoca Cloudflare ni crea o modifica recursos.

Muestra nombres, IDs, estado HTTP y, ante un error, un código y mensaje breves
extraídos del cuerpo, con las credenciales eliminadas. Nunca imprime ni guarda la
clave, encabezados ni el cuerpo completo de la respuesta.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.report_util import emit  # noqa: E402  pylint: disable=wrong-import-position
DEFAULT_ENDPOINT = "https://api.smith.langchain.com"
PATH = "/api/v1/workspaces"
TIMEOUT_SECONDS = 20.0
MAX_MESSAGE_CHARS = 200
MAX_CODE_CHARS = 60
REDACTED = "[redacted]"

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
QUOTES = "'\"`‘’“”"
HEADER_PATTERN = re.compile(
    r"(?i)\b(x-api-key|authorization|x-tenant-id|x-organization-id|cookie)\b"
    r"\s*[:=]\s*\S+")
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+\S+")
TOKEN_PATTERN = re.compile(r"\b(?:lsv2_\w+|ls__\w+|sk-[\w-]{8,})\b")
LONG_SECRET_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")
CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]+")

CONFIRMED = {
    401: ["La petición llegó al servidor de LangSmith y la credencial no fue "
          "aceptada (401)."],
    403: ["La petición llegó al servidor de LangSmith y fue rechazada con 403: la "
          "credencial se reconoció pero no tiene acceso a este recurso."],
}
POSSIBLE_CAUSES = {
    401: [
        "La clave está revocada, vencida, mal copiada o es de otro tipo.",
        "El endpoint corresponde a otra región o instancia que la de la clave.",
        "Una clave de ámbito de organización puede requerir X-Organization-Id.",
    ],
    403: [
        "La clave no tiene el permiso organization:read-metadata.",
        "Una clave de organización o de servicio puede requerir X-Organization-Id "
        "o un workspace (X-Tenant-Id); este diagnóstico no envió X-Tenant-Id y la "
        "ausencia del encabezado no permite concluir si el workspace es necesario.",
        "La clave pertenece a otra organización o región (revise el endpoint).",
    ],
}
UNCONFIRMED_NOTE = ("La respuesta por sí sola no distingue entre estas causas; "
                    "no están confirmadas.")


def _has_space_or_quote(value):
    """Problemas locales de formato, solo como categorías (sin mostrar el valor)."""
    problems = []
    if value != value.strip():
        problems.append("espacios_en_los_extremos")
    if re.search(r"\s", value.strip()):
        problems.append("espacios_internos")
    if any(char in QUOTES for char in value):
        problems.append("comillas")
    return problems


def validate_inputs(env):
    """Valida el formato localmente; devuelve ``(resumen, hay_errores)``.

    El resumen contiene solo ``válido``, ``inválido`` o ``no definido`` y los
    nombres de las categorías de problema, nunca los valores.
    """
    summary, invalid = {}, False

    def record(name, problems, defined):
        nonlocal invalid
        if not defined:
            summary[name] = {"estado": "no definido"}
        elif problems:
            summary[name] = {"estado": "inválido", "problemas": problems}
            invalid = True
        else:
            summary[name] = {"estado": "válido"}

    key = env.get("LANGSMITH_API_KEY") or ""
    record("LANGSMITH_API_KEY", _has_space_or_quote(key), bool(key))
    endpoint = env.get("LANGSMITH_ENDPOINT") or ""
    problems = _has_space_or_quote(endpoint) if endpoint else []
    if endpoint and not problems:
        parsed = httpx.URL(endpoint) if "://" in endpoint else None
        if parsed is None or parsed.scheme != "https" or not parsed.host:
            problems.append("no_es_url_https")
    record("LANGSMITH_ENDPOINT", problems, bool(endpoint))
    for name in ("LANGSMITH_ORGANIZATION_ID", "LANGSMITH_WORKSPACE_ID"):
        value = env.get(name) or ""
        problems = _has_space_or_quote(value) if value else []
        if value and not problems and not UUID_PATTERN.match(value):
            problems.append("no_es_uuid")
        record(name, problems, bool(value))
    return summary, invalid


def sanitize(text, secrets=()):
    """Elimina credenciales y encabezados de un texto y lo limita en longitud."""
    clean = str(text)
    for secret in secrets:
        if secret:
            clean = clean.replace(secret, REDACTED)
    clean = HEADER_PATTERN.sub(REDACTED, clean)
    clean = BEARER_PATTERN.sub(REDACTED, clean)
    clean = TOKEN_PATTERN.sub(REDACTED, clean)
    clean = LONG_SECRET_PATTERN.sub(REDACTED, clean)
    clean = CONTROL_PATTERN.sub(" ", clean).strip()
    return clean[:MAX_MESSAGE_CHARS]


def _text_of(value):
    """Texto breve de un valor JSON: cadena, o primer mensaje de lista o dict."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _text_of(value[0])
    if isinstance(value, dict):
        for field in ("msg", "message", "detail", "error"):
            if field in value:
                return _text_of(value[field])
    return None


def extract_error(response, secrets=()):
    """Código y mensaje útiles de un cuerpo de error, ya sanitizados y acotados.

    Nunca devuelve el cuerpo completo: solo ``code`` y ``message`` si existen.
    """
    found = {"content_type": response.headers.get("content-type", "")[:60]}
    try:
        body = response.json()
    except ValueError:
        found["body_is_json"] = False
        return found
    found["body_is_json"] = True
    if not isinstance(body, dict):
        return found
    code = body.get("code") or (
        body.get("error") if isinstance(body.get("error"), str) else None)
    if isinstance(code, (str, int)):
        found["code"] = sanitize(code, secrets)[:MAX_CODE_CHARS]
    message = _text_of(body.get("detail") or body.get("message")
                       or body.get("msg") or body.get("error"))
    if message:
        found["message"] = sanitize(message, secrets)
    return found


def _workspace_row(item):
    """Solo campos no sensibles: id, nombre, organización y estado."""
    return {"id": item.get("id"), "display_name": item.get("display_name"),
            "organization_id": item.get("organization_id"),
            "is_deleted": item.get("is_deleted"),
            "is_personal": item.get("is_personal")}


def _base(endpoint):
    """URL base sin barra final ni sufijo ``/api/v1``."""
    base = (endpoint or DEFAULT_ENDPOINT).rstrip("/")
    return base[: -len("/api/v1")] if base.endswith("/api/v1") else base


def _success(report, response, env):
    """Completa el informe con la lista de workspaces."""
    try:
        data = response.json()
    except ValueError:
        report["error_type"] = "InvalidJson"
        return
    rows = [_workspace_row(item) for item in data if isinstance(item, dict)]
    report["workspaces"] = rows
    configured = env.get("LANGSMITH_WORKSPACE_ID")
    report["configured_workspace_id_listed"] = (
        any(row["id"] == configured for row in rows) if configured else None)
    report["passed"] = True


def fetch_workspaces(env, transport=None):
    """Valida localmente y, si todo es válido, hace una única consulta.

    :param env: Mapeo tipo ``os.environ``.
    :return: Informe sin secretos; ``http_status`` es ``None`` si no hubo respuesta.
    """
    checks, invalid = validate_inputs(env)
    report = {"local_validation": checks, "http_status": None, "workspaces": [],
              "passed": False, "request_sent": False}
    if invalid:
        report["stage"] = "local_validation_failed"
        return report
    base = _base(env.get("LANGSMITH_ENDPOINT"))
    headers = {"X-API-Key": env["LANGSMITH_API_KEY"]}
    if env.get("LANGSMITH_ORGANIZATION_ID"):
        headers["X-Organization-Id"] = env["LANGSMITH_ORGANIZATION_ID"]
    report.update(endpoint_host=httpx.URL(base).host, path=PATH,
                  header_names_sent=sorted(headers), request_sent=True)
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS) as client:
            response = client.get(base + PATH, headers=headers)
    except httpx.HTTPError as error:
        report["error_type"] = type(error).__name__
        return report
    status = report["http_status"] = response.status_code
    if status == 200:
        _success(report, response, env)
        return report
    secrets = [env["LANGSMITH_API_KEY"], env.get("LANGSMITH_ORGANIZATION_ID", "")]
    report["error"] = extract_error(response, secrets)
    if status in CONFIRMED:
        report["confirmed"] = CONFIRMED[status]
        report["possible_causes_unconfirmed"] = POSSIBLE_CAUSES[status] + [
            UNCONFIRMED_NOTE]
    return report


def main():
    """Punto de entrada."""
    if not os.environ.get("LANGSMITH_API_KEY"):
        print("Falta LANGSMITH_API_KEY en este PowerShell.")
        return 2
    report = fetch_workspaces(os.environ)
    report["date_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return emit(report, "langsmith-check", "workspaces")


if __name__ == "__main__":
    sys.exit(main())
