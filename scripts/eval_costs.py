"""Evaluación baseline/optimizada con el mismo conjunto fijo de preguntas.

Modos:
  (sin --run)   calcula llamadas máximas y costo estimado; sin red.
  --run fake    valida el arnés con el modelo simulado; sin red ni costo real.
  --run real    llama a Cloudflare. Exige --max-calls y --max-usd, y que
                --max-calls cubra el máximo del plan. Lee solo variables de
                entorno (nunca .env); no imprime valores de secretos.
La calidad se mide con el criterio de data/eval_questions.json, igual para ambas.
"""

import argparse
import contextlib
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# pylint: disable=wrong-import-position
from fastapi.testclient import TestClient  # noqa: E402

import app.main as app_main  # noqa: E402
from app.agent import (INVALID_OUTPUT_ANSWER, MISSING_ARGS_ANSWER,  # noqa: E402
                       STEP_LIMIT_ANSWER, UNKNOWN_TOOL_ANSWER)
from app.budget import BudgetGuard, wrap_models  # noqa: E402
from app.config import load_config  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pricing import Pricing, PricingError  # noqa: E402
from app.router import choose_route  # noqa: E402

VARIANTS = {
    "baseline": {"ROUTING": "false", "HISTORY_WINDOW": "50"},
    "optimized": {"ROUTING": "true", "HISTORY_WINDOW": "6"},
}
# Supuestos de estimación (ver doc/evaluacion-costos.md).
EXPECTED_CALLS_PER_QUESTION = 3  # 2 del directorio + 1 del revisor
WORST_INPUT_TOKENS = 1500
# Basado en la prueba real del 19-nov-2026 (1 consulta, 3 llamadas): 214 tokens de
# entrada y 23 de salida por llamada en promedio, con margen para preguntas de
# listas, comparaciones e historial. Es una muestra pequeña, no una garantía.
EXPECTED_INPUT_TOKENS = 300
EXPECTED_OUTPUT_TOKENS = 60
REQUIRED_MODEL_ENV = ("MODEL_SMALL", "MODEL_LARGE")
# Un tope menor a esto rechazaría incluso la consulta más simple (el prompt del
# directorio por sí solo se estima en cientos de tokens): no deja medir nada.
MIN_INPUT_TOKENS_CAP = 1500
PROTOCOL_FAILURES = (INVALID_OUTPUT_ANSWER, UNKNOWN_TOOL_ANSWER,
                     MISSING_ARGS_ANSWER, STEP_LIMIT_ANSWER)
REAL_ENV = ("CF_ACCOUNT_ID", "CF_API_TOKEN")
PASSTHROUGH = ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN", "CF_AIG_TOKEN",
               "MODEL_SMALL", "MODEL_LARGE", "MODEL_MAX_TOKENS",
               "MODEL_EXTRA_PARAMS", "AGENT_MAX_STEPS")


def _load_questions():
    """Lee el conjunto fijo de preguntas."""
    path = ROOT / "data" / "eval_questions.json"
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def _env_for(variant, provider, api_key):
    """Entorno de una variante; los secretos de Cloudflare vienen del entorno."""
    env = {"MODEL_PROVIDER": provider, "ENVIRONMENT": "development",
           "LANGSMITH_TRACING": "false", "HIDE_INPUTS": "true",
           "HIDE_OUTPUTS": "true", "API_KEYS": f"eval:{api_key}",
           "RATE_LIMIT_PER_MINUTE": "1000", "CACHE_TTL_SECONDS": "0",
           "EMPLOYEES_PATH": str(ROOT / "data" / "employees.json"),
           "PRICES_PATH": str(ROOT / "data" / "model_prices.json"),
           **VARIANTS[variant]}
    for name in PASSTHROUGH:
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


def select(questions, only, variants):
    """Filtra preguntas y variantes; valida los nombres."""
    ids = {item["id"] for item in questions}
    wanted = [part for part in (only or "").split(",") if part]
    names = [part for part in (variants or "").split(",") if part]
    unknown = [part for part in wanted if part not in ids] + [
        part for part in names if part not in VARIANTS]
    if unknown:
        raise ValueError("Valores desconocidos: " + ", ".join(unknown))
    return ([item for item in questions if not wanted or item["id"] in wanted],
            names or list(VARIANTS))


def max_calls_per_question(steps):
    """Máximo de llamadas por pregunta: una por paso y, si cabe, la del revisor.

    El revisor solo actúa con evidencia, que exige un paso con herramienta y otro
    con la respuesta; con un solo paso no puede intervenir.
    """
    return steps + (1 if steps >= 2 else 0)


def build_plan(questions, variants=None):
    """Calcula llamadas máximas y costo estimado por variante (sin red)."""
    pricing = Pricing.from_file(ROOT / "data" / "model_prices.json")
    sample = load_config(_env_for("optimized", "fake", "plan-only-not-a-key-0001"))
    plan = {"questions": len(questions), "variants": {},
            "models": {name: {
                "id": model,
                "usd_per_million": {
                    "input": pricing.cost(model, 1_000_000, 0),
                    "output": pricing.cost(model, 0, 1_000_000)}}
                for name, model in (("small", sample.model_small),
                                    ("large", sample.model_large))}}
    for variant in variants or VARIANTS:
        config = load_config(_env_for(variant, "fake", "plan-only-not-a-key-0001"))
        per_question_max = max_calls_per_question(config.agent_max_steps)
        expected_per_question = min(EXPECTED_CALLS_PER_QUESTION, per_question_max)
        worst = expected = 0.0
        for item in questions:
            model = choose_route(item["question"], config).model
            worst += per_question_max * pricing.reserve_cost(
                model, WORST_INPUT_TOKENS, config.model_max_tokens)
            expected += expected_per_question * pricing.cost(
                model, EXPECTED_INPUT_TOKENS, EXPECTED_OUTPUT_TOKENS, False)
        plan["variants"][variant] = {
            "max_calls": len(questions) * per_question_max,
            "expected_calls": len(questions) * expected_per_question,
            "worst_case_usd": round(worst, 4), "expected_usd": round(expected, 4)}
    totals = list(plan["variants"].values())
    for key in ("max_calls", "expected_calls", "worst_case_usd", "expected_usd"):
        plan[key + "_total"] = round(sum(v[key] for v in totals), 4)
    return plan


def evaluate_answer(item, status, answer):
    """Criterio único de calidad, igual para todas las variantes."""
    text = (answer or "").casefold()
    included = all(part.casefold() in text for part in item["must_include"])
    excluded = not any(part.casefold() in text for part in item["must_exclude"])
    return status == 200 and included and excluded


def _ask(client, api_key, item):
    """Envía una pregunta y devuelve la fila de resultados."""
    body = {"question": item["question"]}
    if item.get("history"):
        body["history"] = item["history"]
    started = time.perf_counter()
    response = client.post("/ask", json=body, headers={"X-API-Key": api_key})
    data = response.json() if response.status_code == 200 else {}
    answer = data.get("answer", "")
    return {
        "id": item["id"], "status": response.status_code,
        "passed": evaluate_answer(item, response.status_code, answer),
        "protocol_failure": answer in PROTOCOL_FAILURES,
        "answer": answer, "route": data.get("route"), "model": data.get("model"),
        "review_status": data.get("review_status"),
        "steps": data.get("steps", 0), "review_calls": data.get("review_calls", 0),
        "calls": data.get("steps", 0) + data.get("review_calls", 0),
        "input_tokens": data.get("input_tokens", 0),
        "output_tokens": data.get("output_tokens", 0),
        "review_input_tokens": data.get("review_input_tokens", 0),
        "review_output_tokens": data.get("review_output_tokens", 0),
        "cost_usd": data.get("cost_usd", 0.0),
        "review_cost_usd": data.get("review_cost_usd", 0.0),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _summarize(rows):
    """Totales por variante."""
    keys = ("calls", "input_tokens", "output_tokens", "review_input_tokens",
            "review_output_tokens", "cost_usd", "review_cost_usd")
    summary = {key: round(sum(row[key] for row in rows), 6) for key in keys}
    summary["passed"] = sum(1 for row in rows if row["passed"])
    summary["protocol_failures"] = sum(1 for row in rows if row["protocol_failure"])
    summary["questions"] = len(rows)
    summary["quality"] = round(summary["passed"] / len(rows), 3)
    return summary


def _install_guard(provider, max_calls, max_usd, max_input):
    """Con proveedor real, las llamadas pasan por un guardián compartido."""
    pricing = Pricing.from_file(ROOT / "data" / "model_prices.json")
    config = load_config(_env_for("baseline", provider, "guard-only-not-a-key-01"))
    guard = BudgetGuard(pricing, max_calls, max_usd, max_input,
                        config.model_max_tokens)
    if provider == "gateway":
        real_build = app_main.build_models
        app_main.build_models = lambda cfg, directory: wrap_models(
            real_build(cfg, directory), guard)
    return guard


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _run_variant(variant, provider, api_key, questions, limits, rows=None):
    """Ejecuta una variante hasta agotar las preguntas o un tope.

    :param limits: ``(guard, calls_before, spent_before, max_calls, max_usd)``.
    :param rows: Lista donde se acumulan las filas (compartida con quien llama para
        conservar resultados parciales si la ejecución se interrumpe).
    :return: Filas de resultados.
    """
    guard, calls, spent, max_calls, max_usd = limits
    config = load_config(_env_for(variant, provider, api_key))
    client = TestClient(create_app(config=config), raise_server_exceptions=False)
    rows = [] if rows is None else rows
    for item in questions:
        if (guard.tripped or spent >= max_usd or calls + max_calls_per_question(
                config.agent_max_steps) > max_calls):
            print(f"Tope alcanzado en {variant}/{item['id']}: se detiene.")
            break
        row = _ask(client, api_key, item)
        calls += row["calls"]
        spent += row["cost_usd"]
        rows.append(row)
        if row["status"] != 200:
            # Un error del proveedor o del control de datos detiene la evaluación.
            print(f"Estado {row['status']} en {variant}/{item['id']}: se detiene.")
            break
    return rows


# pylint: disable-next=too-many-locals
def run(provider, max_calls, max_usd, max_input=3000, selection=None):
    """Ejecuta las variantes respetando el límite de llamadas y el presupuesto."""
    questions, variants = selection or (_load_questions(), list(VARIANTS))
    api_key = secrets.token_urlsafe(24)
    guard = _install_guard(provider, max_calls, max_usd, max_input)
    output = {}
    calls = 0
    spent = 0.0
    try:
        for variant in variants:
            rows = []
            output[variant] = {"rows": rows, "summary": {}}
            _run_variant(variant, provider, api_key, questions,
                         (guard, calls, spent, max_calls, max_usd), rows)
            calls += sum(row["calls"] for row in rows)
            spent += sum(row["cost_usd"] for row in rows)
            output[variant]["summary"] = _summarize(rows) if rows else {}
    except BaseException as error:
        # Resultados parciales: se entregan a quien llama para guardarlos.
        for data in output.values():
            if data["rows"] and not data["summary"]:
                data["summary"] = _summarize(data["rows"])
        error.partial = (output, guard)
        raise
    return output, calls, spent, guard


def _prepare(args):
    """Valida argumentos, entorno y precios antes de cualquier ejecución.

    :return: ``(código_de_salida o None, plan, selección)``.
    """
    if args.max_input_tokens < MIN_INPUT_TOKENS_CAP:
        print(f"--max-input-tokens={args.max_input_tokens} es demasiado bajo: "
              f"rechazaría todas las llamadas. Use al menos {MIN_INPUT_TOKENS_CAP}.")
        return 2, None, None
    try:
        selection = select(_load_questions(), args.only, args.variants)
        plan = build_plan(*selection)
    except ValueError as error:
        print(error)
        return 2, None, None
    except PricingError as error:
        print("Modelo sin precio verificado en data/model_prices.json:", error)
        return 2, None, None
    if args.run == "real":
        missing = [name for name in REAL_ENV + REQUIRED_MODEL_ENV
                   if not os.environ.get(name)]
        if missing:
            print("Faltan variables de entorno:", ", ".join(missing))
            return 2, None, None
        if args.max_calls < plan["max_calls_total"] or args.max_usd <= 0:
            print(f"Autorización insuficiente: --max-calls debe ser al menos "
                  f"{plan['max_calls_total']} y --max-usd mayor que 0.")
            return 2, None, None
    return None, plan, selection


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", choices=("fake", "real"))
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--max-usd", type=float, default=0.0)
    parser.add_argument("--max-input-tokens", type=int, default=3000,
                        help="tope de la ESTIMACIÓN de entrada por llamada, en tokens "
                             "(por omisión 3000; mínimo 1500)")
    parser.add_argument("--only", default="", help="ids de preguntas, p. ej. Q01,Q04")
    parser.add_argument("--variants", default="", help="baseline,optimized")
    args = parser.parse_args()
    code, plan, selection = _prepare(args)
    if code is not None:
        return code
    if args.run is None:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    return _execute(args, plan, selection)


# pylint: disable-next=too-many-locals
def _execute(args, plan, selection):
    """Ejecuta la evaluación y guarda resultados y registro de eventos.

    :return: 0 si terminó completa; 1 si se detuvo antes (parciales guardados).
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = ROOT / "evidence" / "costs" / f"{stamp}-{args.run}"
    folder.mkdir(parents=True, exist_ok=False)  # carpeta nueva en cada ejecución
    # El log JSON de la aplicación (sin preguntas ni secretos) va a un archivo.
    interrupted = None
    with (folder / "app-events.log").open("w", encoding="utf-8") as events:
        with contextlib.redirect_stdout(events):
            try:
                output, calls, spent, guard = run(
                    "gateway" if args.run == "real" else "fake",
                    args.max_calls or plan["max_calls_total"],
                    args.max_usd or 1.0, args.max_input_tokens, selection)
            except BaseException as error:  # pylint: disable=broad-exception-caught
                if not hasattr(error, "partial"):
                    raise
                output, guard = error.partial
                rows = [row for data in output.values() for row in data["rows"]]
                calls = sum(row["calls"] for row in rows)
                spent = sum(row["cost_usd"] for row in rows)
                interrupted = type(error).__name__
    wanted = len(selection[0])
    complete = (interrupted is None and guard.tripped is None and all(
        len(data["rows"]) == wanted and all(
            row["status"] == 200 for row in data["rows"])
        for data in output.values()))
    result = {"date_utc": stamp, "mode": args.run, "plan": plan,
              "complete": complete, "interrupted_by": interrupted,
              "calls_made": calls, "cost_usd_reported": round(spent, 6),
              "simulated": args.run == "fake",
              "budget": {"max_calls": guard.max_calls, "max_usd": guard.max_usd,
                         "max_input_tokens": guard.max_input_tokens,
                         "calls_through_guard": guard.calls,
                         "spent_usd_from_usage": round(guard.spent_usd, 8),
                         "tripped": guard.tripped}, **output}
    (folder / "results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for variant, data in output.items():
        print(variant, json.dumps(data["summary"], ensure_ascii=False))
    print("Resultados en", folder.relative_to(ROOT),
          "(completo)" if complete else "(PARCIAL: la ejecución se detuvo)")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
