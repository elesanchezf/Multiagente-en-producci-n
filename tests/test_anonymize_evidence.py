"""Pruebas de la anonimización de evidencias (rutas ficticias)."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "anonymize_evidence.py"
USER_DIR = "C:" + "\\" + "Users" + "\\" + "Persona"


def _module():
    spec = importlib.util.spec_from_file_location("anonymize_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_personal_paths_are_replaced_and_the_copy_is_marked():
    """Las rutas de usuario se sustituyen y la copia se identifica."""
    module = _module()
    root = USER_DIR + "\\Documents\\Codex\\x\\work\\Multiagente-en-produccion"
    text = f"rootdir: {root}\nFile \"{USER_DIR}\\AppData\\Roaming\\uv\\socket.py\"\n"
    result = module.anonymize_text(text)
    assert result.startswith("[ANONIMIZADO]")
    assert "Persona" not in result
    assert "<RAIZ_DEL_PROYECTO>" in result and "<USUARIO_LOCAL>" in result


def test_the_copy_has_a_distinct_name():
    """El nombre de la copia no coincide con el del original."""
    module = _module()
    assert module.anonymized_path(Path("a/pytest.txt")).name == "pytest.anonimizado.txt"
