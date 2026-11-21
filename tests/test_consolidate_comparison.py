"""Pruebas de la consolidación de comparaciones reales (datos ficticios)."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "consolidate_comparison.py"


@pytest.fixture(name="module")
def module_fixture(tmp_path, monkeypatch):
    """Carga el script apuntando a una carpeta temporal con dos preguntas."""
    spec = importlib.util.spec_from_file_location("consolidate_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "eval_questions.json").write_text(
        json.dumps({"questions": [{"id": "Q1"}, {"id": "Q2"}]}), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "COSTS", tmp_path / "costs")
    return module


def _row(qid, status=200, passed=True, protocol=False, cost=0.1):
    return {"id": qid, "status": status, "passed": passed, "protocol_failure": protocol,
            "calls": 2, "input_tokens": 10, "output_tokens": 5,
            "review_input_tokens": 4, "review_output_tokens": 1,
            "cost_usd": cost, "review_cost_usd": 0.01, "latency_ms": 100.0,
            "model": "m"}


def _write(module, name, data):
    folder = module.COSTS / name
    folder.mkdir(parents=True)
    (folder / "results.json").write_text(json.dumps(data), encoding="utf-8")


def _runs(module, continuation_rows):
    _write(module, "a", {
        "calls_made": 4, "budget": {"calls_through_guard": 5},
        "baseline": {"rows": [_row("Q1"), _row("Q2", protocol=True)]},
        "optimized": {"rows": [_row("Q1"), _row("Q2", status=502, passed=False)]}})
    _write(module, "b", {"complete": True,
                         "optimized": {"rows": continuation_rows}})


def test_each_question_appears_once_and_failed_attempt_is_kept_apart(module):
    """El intento 502 no entra en los totales y queda registrado aparte."""
    _runs(module, [_row("Q2", cost=0.2)])
    result = module.consolidate("a", "b")
    assert [row["id"] for row in result["optimized"]["rows"]] == ["Q1", "Q2"]
    assert result["excluded_attempts"][0]["status"] == 502
    assert result["unrecorded_calls_through_guard"] == {"a": 1}
    assert result["optimized"]["summary"]["cost_usd"] == pytest.approx(0.3)
    assert result["baseline"]["summary"]["protocol_failures"] == 1
    assert result["baseline"]["summary"]["passed_without_protocol_failure"] == 1
    assert result["baseline"]["summary"]["criterion_passed"] == 2


def test_duplicate_or_missing_question_is_rejected(module):
    """Una pregunta repetida o ausente impide la consolidación."""
    _runs(module, [_row("Q1")])
    with pytest.raises(module.ConsolidationError):
        module.consolidate("a", "b")


def test_incomplete_continuation_is_rejected(module):
    """Una continuación incompleta no se consolida."""
    _runs(module, [_row("Q2")])
    path = module.COSTS / "b" / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["complete"] = False
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(module.ConsolidationError):
        module.consolidate("a", "b")
