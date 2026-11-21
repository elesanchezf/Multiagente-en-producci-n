"""Pruebas unitarias de la prueba de humo ``scripts/smoke.py`` (sesion 4).

Supuestos de interfaz: ``main(argv, env, send=None)`` devuelve el codigo de
salida (0 si las tres comprobaciones pasan, 1 si alguna falla). ``argv``
solo trae la URL; la clave se lee de ``env["SMOKE_API_KEY"]``. ``send(method,
url, headers, payload)`` devuelve el codigo HTTP y se sustituye aqui por un
transporte simulado, por lo que no hay red. La clave es ficticia.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke.py"
KEY = "fake-smoke-key-000000"
URL = "https://hr-assistant.example.test"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _transport(ask_with_key_status=200):
    calls = []

    def send(method, url, headers, payload):
        del payload
        calls.append((method, url, dict(headers or {})))
        if url.endswith("/health"):
            return 200
        if not (headers or {}).get("X-API-Key"):
            return 401
        return ask_with_key_status

    return send, calls


def test_three_passing_checks_print_ok_and_exit_with_zero(capsys):
    """Tres comprobaciones exitosas imprimen [OK] tres veces y salen con 0."""
    send, calls = _transport()
    code = _load_smoke().main([URL], {"SMOKE_API_KEY": KEY}, send)
    output = capsys.readouterr().out
    assert code == 0
    assert output.count("[OK]") == 3
    assert "[FAIL]" not in output
    assert len(calls) == 3
    assert KEY not in output


def test_a_failing_check_prints_fail_exits_with_one_and_hides_the_key(capsys):
    """Una comprobacion fallida imprime [FAIL], sale con 1 y no muestra la clave."""
    send, _calls = _transport(ask_with_key_status=500)
    code = _load_smoke().main([URL], {"SMOKE_API_KEY": KEY}, send)
    output = capsys.readouterr().out
    assert code == 1
    assert output.count("[OK]") == 2
    assert output.count("[FAIL]") == 1
    assert KEY not in output
