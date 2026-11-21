"""Consolida una comparación real hecha en dos ejecuciones, sin llamadas ni red.

Lee los ``results.json`` originales (que no se modifican) y escribe en una carpeta
nueva ``consolidado-<primera>+<continuación>``:

* baseline: todas las filas de la primera ejecución;
* optimized: las filas con estado 200 de la primera más las de la continuación;
* los intentos con estado distinto de 200 se conservan aparte y no entran en los
  totales (su consumo es desconocido).

Verifica que cada pregunta del conjunto fijo aparezca exactamente una vez por
variante. Las sumas usan ``math.fsum`` sobre los valores originales, sin redondeos
intermedios; solo la presentación en el Markdown redondea.
"""

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COSTS = ROOT / "evidence" / "costs"
SUM_KEYS = ("calls", "input_tokens", "output_tokens", "review_input_tokens",
            "review_output_tokens", "cost_usd", "review_cost_usd")


class ConsolidationError(Exception):
    """Los registros no permiten una comparación válida."""


def _load(name):
    path = COSTS / name / "results.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _questions():
    path = ROOT / "data" / "eval_questions.json"
    return [item["id"] for item in json.loads(
        path.read_text(encoding="utf-8"))["questions"]]


def _check_once(variant, rows, expected):
    ids = [row["id"] for row in rows]
    if sorted(ids) != sorted(expected):
        missing = sorted(set(expected) - set(ids))
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        raise ConsolidationError(
            f"{variant}: faltan {missing} o se repiten {repeated}")


def summarize(rows):
    """Totales exactos de una variante; el revisor ya está incluido en ellos."""
    summary = {key: math.fsum(row[key] for row in rows) for key in SUM_KEYS}
    summary["questions"] = len(rows)
    summary["criterion_passed"] = sum(1 for row in rows if row["passed"])
    summary["protocol_failures"] = sum(1 for row in rows if row["protocol_failure"])
    summary["passed_without_protocol_failure"] = sum(
        1 for row in rows if row["passed"] and not row["protocol_failure"])
    summary["quality_by_criterion"] = summary["criterion_passed"] / len(rows)
    latencies = [row["latency_ms"] for row in rows]
    summary["latency_ms_mean"] = math.fsum(latencies) / len(latencies)
    summary["latency_ms_median"] = statistics.median(latencies)
    summary["latency_ms_max"] = max(latencies)
    return summary


def consolidate(first_name, continuation_name):
    """Construye la comparación final y la devuelve como diccionario."""
    first, cont = _load(first_name), _load(continuation_name)
    expected = _questions()
    baseline = first["baseline"]["rows"]
    kept = [row for row in first["optimized"]["rows"] if row["status"] == 200]
    excluded = [{**row, "source": first_name, "variant": "optimized"}
                for row in first["optimized"]["rows"] if row["status"] != 200]
    cont_rows = cont["optimized"]["rows"]
    if not cont.get("complete") or any(r["status"] != 200 for r in cont_rows):
        raise ConsolidationError("La continuación no está completa")
    optimized = kept + cont_rows
    _check_once("baseline", baseline, expected)
    _check_once("optimized", optimized, expected)
    order = {qid: index for index, qid in enumerate(expected)}
    sources = {row["id"]: first_name for row in kept}
    return {
        "sources": {"first": first_name, "continuation": continuation_name},
        "notes": [
            "optimized combina dos ejecuciones: Q01-Q04 de la primera y Q05-Q12 "
            "de la continuación.",
            "El tiempo de espera del gateway cambió de 30 a 60 s entre ambas.",
            "Costos estimados con data/model_prices.json; no son factura.",
            "Los intentos fallidos no entran en los totales; su consumo es "
            "desconocido."],
        "excluded_attempts": excluded,
        "unrecorded_calls_through_guard": {
            first_name: first["budget"]["calls_through_guard"] - first["calls_made"]},
        "baseline": {"rows": sorted(baseline, key=lambda r: order[r["id"]]),
                     "summary": summarize(baseline)},
        "optimized": {"rows": sorted(
            [{**row, "source": sources.get(row["id"], continuation_name)}
             for row in optimized], key=lambda r: order[r["id"]]),
            "summary": summarize(optimized)},
    }


METRICS = (
    ("Preguntas", "questions", "{:d}"),
    ("Aprobadas por criterio", "criterion_passed", "{:d}"),
    ("Aprobadas sin falla de protocolo", "passed_without_protocol_failure", "{:d}"),
    ("Fallas de protocolo", "protocol_failures", "{:d}"),
    ("Llamadas registradas", "calls", "{:.0f}"),
    ("Tokens de entrada (con revisor)", "input_tokens", "{:.0f}"),
    ("Tokens de salida (con revisor)", "output_tokens", "{:.0f}"),
    ("  de ellos, entrada del revisor", "review_input_tokens", "{:.0f}"),
    ("  de ellos, salida del revisor", "review_output_tokens", "{:.0f}"),
    ("Costo estimado USD (con revisor)", "cost_usd", "{:.6f}"),
    ("  del cual, revisor USD", "review_cost_usd", "{:.6f}"),
    ("Latencia media ms", "latency_ms_mean", "{:.0f}"),
    ("Latencia mediana ms", "latency_ms_median", "{:.0f}"),
    ("Latencia máxima ms", "latency_ms_max", "{:.0f}"),
)


def _mark(row):
    text = "aprobó" if row["passed"] else "NO aprobó"
    return text + (" (falla de protocolo)" if row["protocol_failure"] else "")


def render_markdown(result):
    """Tabla de lectura; solo aquí se redondea."""
    lines = ["# Comparación consolidada (scripts/consolidate_comparison.py)", ""]
    lines += [f"- {note}" for note in result["notes"]] + [""]
    lines += ["| Métrica | baseline (70B) | optimized (Gemma + enrutamiento) |",
              "| --- | --- | --- |"]
    base, opt = result["baseline"]["summary"], result["optimized"]["summary"]
    for label, key, fmt in METRICS:
        lines.append(f"| {label} | {fmt.format(base[key])} | {fmt.format(opt[key])} |")
    lines += ["", "| Pregunta | baseline | optimized | modelo optimized |",
              "| --- | --- | --- | --- |"]
    for left, right in zip(result["baseline"]["rows"], result["optimized"]["rows"]):
        model = (right["model"] or "").split("/")[-1]
        lines.append(f"| {left['id']} | {_mark(left)} | {_mark(right)} | {model} |")
    for attempt in result["excluded_attempts"]:
        lines += ["", f"Intento excluido: {attempt['variant']}/{attempt['id']} de "
                      f"{attempt['source']}, estado {attempt['status']}, "
                      f"{attempt['latency_ms']} ms; consumo desconocido."]
    return "\n".join(lines) + "\n"


def main():
    """Escribe la consolidación en una carpeta nueva."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("first")
    parser.add_argument("continuation")
    args = parser.parse_args()
    try:
        result = consolidate(args.first, args.continuation)
    except ConsolidationError as error:
        print("Consolidación rechazada:", error)
        return 1
    folder = COSTS / f"consolidado-{args.first}+{args.continuation}"
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "consolidated.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "resultado.md").write_text(render_markdown(result), encoding="utf-8")
    print("Escrito en", folder.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
