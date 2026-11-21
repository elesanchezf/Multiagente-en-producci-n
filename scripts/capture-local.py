"""Ejecuta el servidor simulado y Playwright juntos; guarda evidencia sin secretos."""

import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    """Verifica disponibilidad, ejecuta E2E y cierra solo el servidor iniciado aquí."""
    root = Path(__file__).resolve().parent.parent
    evidence = root / "evidence"
    env = {**os.environ, "MODEL_PROVIDER": "fake", "ENVIRONMENT": "development",
           "LANGSMITH_TRACING": "false", "API_KEYS": "evidence:local-demo-only-2026",
           "RATE_LIMIT_PER_MINUTE": "300", "E2E_API_KEY": "local-demo-only-2026",
           "PLAYWRIGHT_BROWSERS_PATH": str(root / ".playwright"),
           "EVIDENCE_DIR": str(evidence / "screenshots")}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (evidence / "multiagent-server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
             "127.0.0.1", "--port", "8014"], cwd=root, env=env,
            stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        )
        try:
            for _ in range(30):
                if server.poll() is not None:
                    raise RuntimeError("El servidor terminó antes de estar disponible")
                try:
                    with urlopen("http://127.0.0.1:8014/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("El servidor local no respondió al health check")
            with (evidence / "multiagent-e2e.txt").open("w", encoding="utf-8") as output:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "e2e", "--base-url",
                     "http://127.0.0.1:8014"], cwd=root, env=env, stdout=output,
                    stderr=subprocess.STDOUT, timeout=120, check=False,
                    creationflags=flags,
                )
            return result.returncode
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
