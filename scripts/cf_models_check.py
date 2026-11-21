"""Comprueba en Cloudflare si los modelos candidatos existen. No ejecuta ningún modelo.

Hace dos consultas de solo lectura al catálogo de Workers AI de la cuenta
(``GET /accounts/{id}/ai/models/search``): no genera texto ni consume cuota de
inferencia. Lee ``CF_ACCOUNT_ID`` y ``CF_API_TOKEN`` solo del entorno y no los imprime.
Muestra por modelo candidato: si aparece, su tarea y las propiedades ``price`` y
``context_window`` que el catálogo informe. Ante un error muestra el estado HTTP y un
código y mensaje breves, saneados; nunca el cuerpo completo ni encabezados.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# pylint: disable=wrong-import-position
from scripts.langsmith_workspaces import extract_error  # noqa: E402
from scripts.report_util import emit  # noqa: E402

API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/models/search"
SEARCHES = ("llama-3.1-8b", "llama-3.3-70b")
CANDIDATES = (
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
)
ACCOUNT_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.I)
SHOWN_PROPERTIES = ("price", "context_window")
MAX_PROPERTY_CHARS = 300


def _validate(env):
    """Formato local (solo válido/inválido/no definido), sin mostrar valores."""
    account = env.get("CF_ACCOUNT_ID") or ""
    token = env.get("CF_API_TOKEN") or ""
    checks = {"CF_ACCOUNT_ID": "no definido", "CF_API_TOKEN": "no definido"}
    if account:
        checks["CF_ACCOUNT_ID"] = (
            "válido" if ACCOUNT_PATTERN.match(account) else "inválido")
    if token:
        spaces = token != token.strip() or re.search(r"\s", token)
        quotes = any(char in "'\"`" for char in token)
        checks["CF_API_TOKEN"] = "inválido" if spaces or quotes else "válido"
    return checks


def _model_row(item):
    """Campos no sensibles de un modelo del catálogo."""
    props = {}
    for prop in item.get("properties") or []:
        if isinstance(prop, dict) and prop.get("property_id") in SHOWN_PROPERTIES:
            text = json.dumps(prop.get("value"), ensure_ascii=False)
            props[prop["property_id"]] = text[:MAX_PROPERTY_CHARS]
    task = item.get("task") if isinstance(item.get("task"), dict) else {}
    return {"name": item.get("name"), "task": task.get("name"), **props}


def check_models(env, transport=None):
    """Consulta el catálogo; devuelve un informe sin secretos."""
    checks = _validate(env)
    report = {"local_validation": checks, "queries": [], "candidates": {},
              "passed": False}
    if "inválido" in checks.values() or "no definido" in checks.values():
        report["stage"] = "local_validation_failed"
        return report
    url = API.format(account=env["CF_ACCOUNT_ID"])
    headers = {"Authorization": f"Bearer {env['CF_API_TOKEN']}"}
    found = {}
    with httpx.Client(transport=transport, timeout=20.0) as client:
        for term in SEARCHES:
            entry = {"search": term, "http_status": None}
            report["queries"].append(entry)
            try:
                response = client.get(url, headers=headers,
                                      params={"search": term, "per_page": 100})
            except httpx.HTTPError as error:
                entry["error_type"] = type(error).__name__
                return report
            entry["http_status"] = response.status_code
            if response.status_code != 200:
                entry["error"] = extract_error(
                    response, [env["CF_API_TOKEN"], env["CF_ACCOUNT_ID"]])
                return report
            for item in (response.json().get("result") or []):
                if isinstance(item, dict) and item.get("name"):
                    found[item["name"]] = _model_row(item)
    for name in CANDIDATES:
        report["candidates"][name] = ({"listed": True, **found[name]}
                                      if name in found else {"listed": False})
    report["passed"] = True
    return report


SCAN_PER_PAGE = 50
SCAN_MAX_PAGES = 20
SCAN_TASK = "Text Generation"
SCAN_PROPERTIES = ("price", "context_window", "beta", "function_calling",
                   "planned_deprecation_date")


def parse_price(value):
    """Precios por millón de tokens (entrada, salida) de la propiedad ``price``."""
    found = {}
    for entry in value if isinstance(value, list) else []:
        unit = str(entry.get("unit", "")).lower() if isinstance(entry, dict) else ""
        number = entry.get("price") if isinstance(entry, dict) else None
        if isinstance(number, (int, float)):
            if "input" in unit:
                found["input"] = number
            elif "output" in unit:
                found["output"] = number
    return found if {"input", "output"} <= set(found) else None


def _scan_row(item):
    """Fila de un modelo de generación de texto: precios y metadatos no sensibles."""
    props = {prop.get("property_id"): prop.get("value")
             for prop in item.get("properties") or [] if isinstance(prop, dict)}
    price = parse_price(props.get("price"))
    row = {"name": item.get("name"), "price_usd_per_million": price}
    for key in SCAN_PROPERTIES[1:]:
        if key in props:
            row[key] = str(props[key])[:60]
    if price:
        row["blended_usd_per_million"] = round(
            (3 * price["input"] + price["output"]) / 4, 4)
    return row


def _fetch_page(client, url, headers, page, secrets):
    """Una página del catálogo: ``(entrada_del_informe, elementos o None)``."""
    entry = {"page": page, "http_status": None}
    try:
        response = client.get(url, headers=headers, params={
            "task": SCAN_TASK, "per_page": SCAN_PER_PAGE, "page": page})
    except httpx.HTTPError as error:
        entry["error_type"] = type(error).__name__
        return entry, None
    entry["http_status"] = response.status_code
    if response.status_code != 200:
        entry["error"] = extract_error(response, secrets)
        return entry, None
    items = [item for item in (response.json().get("result") or [])
             if isinstance(item, dict) and item.get("name")]
    return entry, items


def scan_text_generation(env, transport=None):
    """Recorre todas las páginas del catálogo de generación de texto (solo lectura).

    La documentación no describe la paginación; se recorre ``page`` hasta que una
    página no aporte modelos nuevos o traiga menos de ``per_page``, con tope de
    páginas, y se informa si el parámetro parece ignorarse o si se alcanzó el tope.
    """
    checks = _validate(env)
    report = {"local_validation": checks, "pages": [], "models": [], "passed": False}
    if "inválido" in checks.values() or "no definido" in checks.values():
        report["stage"] = "local_validation_failed"
        return report
    url = API.format(account=env["CF_ACCOUNT_ID"])
    headers = {"Authorization": f"Bearer {env['CF_API_TOKEN']}"}
    secrets = [env["CF_API_TOKEN"], env["CF_ACCOUNT_ID"]]
    seen = {}
    with httpx.Client(transport=transport, timeout=20.0) as client:
        for page in range(1, SCAN_MAX_PAGES + 1):
            entry, items = _fetch_page(client, url, headers, page, secrets)
            report["pages"].append(entry)
            if items is None:
                return report
            new = [item for item in items if item["name"] not in seen]
            entry.update(returned=len(items), new=len(new))
            seen.update({item["name"]: _scan_row(item) for item in new})
            if not new:
                report["pagination_ignored_or_finished"] = True
                break
            if len(items) < SCAN_PER_PAGE:
                break
        else:
            report["page_cap_reached"] = True
    rows = sorted(seen.values(), key=lambda row: (
        row.get("blended_usd_per_million") is None,
        row.get("blended_usd_per_million") or 0))
    report.update(models=rows, total_models=len(rows), passed=True,
                  without_parseable_price=sum(
                      1 for row in rows if not row["price_usd_per_million"]))
    return report


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scan", action="store_true",
                        help="lista todos los modelos de generación de texto")
    args = parser.parse_args()
    if args.scan:
        report = scan_text_generation(os.environ)
        report["date_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return emit(report, "cloudflare-check", "scan")
    report = check_models(os.environ)
    report["date_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return emit(report, "cloudflare-check", "models")


if __name__ == "__main__":
    sys.exit(main())
