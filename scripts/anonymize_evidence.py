"""Genera copias anonimizadas de evidencias de texto para entregar.

Sustituye rutas personales de Windows por marcadores. El original no se modifica ni
se versiona; la copia se llama ``<nombre>.anonimizado<extensión>`` y empieza con una
línea que la identifica como anonimizada.

Uso: python scripts/anonymize_evidence.py archivo1.txt archivo2.txt ...
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ("[ANONIMIZADO] Copia para entrega: se sustituyeron rutas y nombres de "
          "usuario locales por marcadores. El original se conserva solo en local.\n")
# De lo más específico a lo más general.
RULES = (
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s'\"]+[\\/]Documents[\\/]Codex"
                r"[\\/][^\s'\"]*?[\\/]work[\\/]Multiagente-en-produccion",
                re.IGNORECASE), "<RAIZ_DEL_PROYECTO>"),
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s'\"]+", re.IGNORECASE),
     "<USUARIO_LOCAL>"),
)


def anonymize_text(text):
    """Aplica las sustituciones y antepone el encabezado."""
    for pattern, marker in RULES:
        text = pattern.sub(marker, text)
    return HEADER + text


def anonymized_path(path):
    """Ruta de la copia anonimizada de ``path``."""
    return path.with_name(f"{path.stem}.anonimizado{path.suffix}")


def main(arguments):
    """Crea las copias; devuelve 1 si algún archivo no existe."""
    status = 0
    for name in arguments:
        path = (ROOT / name) if not Path(name).is_absolute() else Path(name)
        if not path.is_file():
            print("No existe:", name)
            status = 1
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        destination = anonymized_path(path)
        destination.write_text(anonymize_text(text), encoding="utf-8")
        print("Escrito:", destination.relative_to(ROOT))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
