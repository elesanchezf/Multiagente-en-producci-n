"""Arranque del servidor para las pruebas de navegador.

Si se indica ``--base-url`` (o ``PYTEST_BASE_URL``) se usa ese servidor, como en CI.
Si no, se inicia uno local con el modelo simulado, en un puerto libre y con una clave
ficticia. El servidor propio nunca recibe credenciales de Cloudflare ni de LangSmith.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "ejemplo-clave-de-prueba-0001"  # ficticia
BLOCKED_PREFIXES = ("CF_", "LANGSMITH_", "LANGCHAIN_")
STARTUP_SECONDS = 30


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(url: str, process: subprocess.Popen) -> bool:
    deadline = time.monotonic() + STARTUP_SECONDS
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def base_url(pytestconfig):
    """URL del producto: la indicada por el usuario o un servidor local simulado."""
    configured = pytestconfig.getoption("base_url")
    if configured:
        yield configured
        return
    os.environ.setdefault("E2E_API_KEY", TEST_KEY)
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(BLOCKED_PREFIXES)
    }
    env.update(
        {
            "ENVIRONMENT": "development",
            "MODEL_PROVIDER": "fake",
            "API_KEYS": f"e2e-client:{os.environ['E2E_API_KEY']}",
            "LANGSMITH_TRACING": "false",
        }
    )
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            if not _wait_for_health(url, process):
                log.seek(0)
                tail = log.read().decode("utf-8", "replace")[-1500:]
                pytest.fail(f"El servidor de pruebas no respondió en /health:\n{tail}")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
