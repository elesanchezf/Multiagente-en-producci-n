"""Prueba HTTP local de concurrencia con modelo simulado y datos ficticios.

Arranca un servidor propio en un puerto local, envía solicitudes simultáneas,
comprueba que cada respuesta corresponde a su propia pregunta y guarda un
resumen sin claves ni textos de preguntas en ``evidence/load``. No carga ``.env``.
"""

import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

PORT = 8015
BASE = f"http://127.0.0.1:{PORT}"
API_KEY = "local-load-demo-only-2026"
TOTAL = int(os.environ.get("LOAD_TOTAL", "300"))
WORKERS = int(os.environ.get("LOAD_WORKERS", "30"))


def _percentile(values, fraction):
    """Percentil por rango más cercano sobre una lista no vacía."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def _one(client, index, employees):
    """Envía una solicitud única y valida que la respuesta sea la suya."""
    employee = employees[index % len(employees)]
    request_id = f"load-{uuid.uuid4().hex[:12]}"
    started = time.perf_counter()
    try:
        response = client.post(
            "/ask", json={"question": employee["id"]},
            headers={"X-API-Key": API_KEY, "X-Request-ID": request_id},
        )
        status = response.status_code
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return {"status": 0, "ms": (time.perf_counter() - started) * 1000,
                "isolated": False, "id_echo": False}
    answer = str(body.get("answer", ""))
    others = [item for item in employees if item["id"] != employee["id"]]
    isolated = (
        status == 200
        and employee["id"] in answer
        and employee["name"] in answer
        and not any(item["name"] in answer for item in others)
        and body.get("request_id") == request_id
    )
    return {"status": status, "ms": (time.perf_counter() - started) * 1000,
            "isolated": isolated,
            "id_echo": response.headers.get("X-Request-ID") == request_id,
            "review": body.get("review_status")}


def main():
    """Ejecuta la carga y escribe el resumen."""
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "evidence" / "load"
    out_dir.mkdir(parents=True, exist_ok=True)
    employees = json.loads((root / "data" / "employees.json").read_text("utf-8"))
    env = {**os.environ, "MODEL_PROVIDER": "fake", "ENVIRONMENT": "development",
           "LANGSMITH_TRACING": "false", "API_KEYS": f"load:{API_KEY}",
           "RATE_LIMIT_PER_MINUTE": "100000"}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (out_dir / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
             "127.0.0.1", "--port", str(PORT)], cwd=root, env=env,
            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            for _ in range(50):
                try:
                    if httpx.get(f"{BASE}/health", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("El servidor local no respondió")
            with httpx.Client(base_url=BASE, timeout=30) as client:
                started = time.perf_counter()
                with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                    results = list(pool.map(
                        lambda i: _one(client, i, employees), range(TOTAL)))
                wall = time.perf_counter() - started
                metrics = client.get(
                    "/metrics", headers={"X-API-Key": API_KEY}).json()
        finally:
            server.terminate()
            server.wait(timeout=10)
    latencies = [item["ms"] for item in results]
    statuses = {}
    for item in results:
        statuses[str(item["status"])] = statuses.get(str(item["status"]), 0) + 1
    summary = {
        "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Local, un proceso uvicorn, modelo simulado, datos ficticios; "
                 "no mide Render, Cloudflare ni LangSmith",
        "requests": TOTAL, "concurrent_workers": WORKERS,
        "status_counts": statuses,
        "errors_non_200": sum(1 for i in results if i["status"] != 200),
        "isolated_correct_responses": sum(1 for i in results if i["isolated"]),
        "request_id_echo_ok": sum(1 for i in results if i["id_echo"]),
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(TOTAL / wall, 1),
        "latency_ms": {
            "min": round(min(latencies), 1),
            "mean": round(statistics.mean(latencies), 1),
            "p50": round(_percentile(latencies, 0.50), 1),
            "p95": round(_percentile(latencies, 0.95), 1),
            "p99": round(_percentile(latencies, 0.99), 1),
            "max": round(max(latencies), 1),
        },
        "server_metrics": {key: metrics.get(key) for key in (
            "requests", "errors", "p95_ms", "cost_usd") if key in metrics},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ok = (summary["errors_non_200"] == 0
          and summary["isolated_correct_responses"] == TOTAL)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
