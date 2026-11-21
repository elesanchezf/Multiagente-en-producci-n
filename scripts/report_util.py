"""Guardado e impresión comunes de los informes de diagnóstico (sin secretos)."""

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def emit(report, folder_name, prefix):
    """Guarda el informe en evidence/<carpeta>/ y lo imprime; devuelve el código."""
    folder = ROOT / "evidence" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = folder / f"{prefix}-{stamp}.json"
    text = json.dumps(report, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    print(text)
    print("Informe:", path.relative_to(ROOT))
    return 0 if report["passed"] else 1
