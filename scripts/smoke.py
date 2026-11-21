"""Prueba de humo del HR Assistant publicado.

Uso: SMOKE_API_KEY=<clave> python scripts/smoke.py <url>

La clave se lee solo de la variable de entorno SMOKE_API_KEY, nunca de un
argumento, y nunca se imprime. Comprueba tres cosas y muestra [OK] o [FAIL]:
/health responde 200, /ask sin clave responde 401 y /ask con clave responde 200.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# Tiempos amplios: el plan gratuito de Render se suspende y tarda en arrancar.
TIMEOUT_SECONDS = 60
HEALTH_ATTEMPTS = 5
HEALTH_WAIT_SECONDS = 10
# Pregunta generica, sin datos de personas.
QUESTION = "How many vacation days are there per year?"


def http_send(method, url, headers, payload):
    """Hace la peticion HTTP y devuelve solo el codigo de estado."""
    body = None
    all_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        all_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=body, headers=all_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:
            return reply.status
    except urllib.error.HTTPError as error:
        return error.code


def _status(send, method, url, headers=None, payload=None):
    """Devuelve el codigo HTTP o None si la peticion no se pudo hacer."""
    try:
        return send(method, url, headers, payload)
    except (OSError, ValueError):
        return None


def _report(label, passed):
    """Imprime el resultado de una comprobacion."""
    print(f"[{'OK' if passed else 'FAIL'}] {label}")
    return passed


def _health_status(send, base):
    """Consulta /health con reintentos mientras el servicio despierta."""
    code = None
    for attempt in range(HEALTH_ATTEMPTS):
        code = _status(send, "GET", f"{base}/health")
        if code == 200:
            break
        if attempt < HEALTH_ATTEMPTS - 1:
            time.sleep(HEALTH_WAIT_SECONDS)
    return code


def main(argv, env, send=None):
    """Corre las tres comprobaciones; devuelve 0 si todas pasan, 1 si no."""
    if len(argv) != 1:
        print("Uso: SMOKE_API_KEY=<clave> python scripts/smoke.py <url>")
        return 1
    key = env.get("SMOKE_API_KEY", "")
    if not key:
        print("Falta la variable de entorno SMOKE_API_KEY.")
        return 1
    send = send or http_send
    base = argv[0].rstrip("/")
    payload = {"question": QUESTION}

    results = [
        _report("/health responde 200", _health_status(send, base) == 200),
        _report(
            "/ask sin clave responde 401",
            _status(send, "POST", f"{base}/ask", {}, payload) == 401,
        ),
        _report(
            "/ask con clave responde 200",
            _status(send, "POST", f"{base}/ask", {"X-API-Key": key}, payload)
            == 200,
        ),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
