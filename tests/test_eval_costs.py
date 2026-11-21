"""Pruebas de las condiciones de la evaluación de costos; no hacen llamadas reales."""

import importlib.util
import json
import shutil
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "eval_costs.py"
REAL_ENV = ("CF_ACCOUNT_ID", "CF_API_TOKEN", "MODEL_SMALL", "MODEL_LARGE")


@pytest.fixture(name="evaluation")
def evaluation_fixture():
    """Carga el script sin ejecutarlo."""
    spec = importlib.util.spec_from_file_location("eval_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_env(monkeypatch):
    for name in REAL_ENV:
        monkeypatch.setenv(name, "valor-ficticio")
    monkeypatch.setenv("MODEL_SMALL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    monkeypatch.setenv("MODEL_LARGE", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")


def _argv(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["eval_costs.py", *args])


def _forbid_run(evaluation, monkeypatch):
    def must_not_run(*_args, **_kwargs):
        raise AssertionError("No debe ejecutarse la evaluación")
    monkeypatch.setattr(evaluation, "run", must_not_run)


def test_the_plan_states_models_prices_and_call_limits(evaluation):
    """El plan informa modelos, precios y máximos antes de cualquier ejecución."""
    plan = evaluation.build_plan(evaluation._load_questions())  # pylint: disable=protected-access
    assert plan["max_calls_total"] == 96 and plan["expected_calls_total"] == 72
    assert plan["models"]["large"]["id"] == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert plan["models"]["large"]["usd_per_million"] == {"input": 0.293,
                                                          "output": 2.253}
    assert plan["expected_usd_total"] < plan["worst_case_usd_total"]


@pytest.mark.parametrize("missing", REAL_ENV)
def test_real_mode_needs_explicit_credentials_and_models(
        evaluation, monkeypatch, missing):
    """Sin credenciales o sin MODEL_SMALL/MODEL_LARGE explícitos no se ejecuta."""
    _set_env(monkeypatch)
    monkeypatch.delenv(missing)
    _forbid_run(evaluation, monkeypatch)
    _argv(monkeypatch, "--run", "real", "--max-calls", "96", "--max-usd", "0.05")
    assert evaluation.main() == 2


def test_real_mode_needs_authorization_limits(evaluation, monkeypatch):
    """Un máximo de llamadas menor al plan, o sin presupuesto, no se ejecuta."""
    _set_env(monkeypatch)
    _forbid_run(evaluation, monkeypatch)
    _argv(monkeypatch, "--run", "real", "--max-calls", "50", "--max-usd", "0.05")
    assert evaluation.main() == 2
    _argv(monkeypatch, "--run", "real", "--max-calls", "96")
    assert evaluation.main() == 2


def test_questions_and_criteria_are_unchanged(evaluation):
    """Las 12 preguntas y sus criterios no cambiaron, incluidos Q06 y Q10."""
    questions = evaluation._load_questions()  # pylint: disable=protected-access
    assert [item["id"] for item in questions] == [f"Q{n:02d}" for n in range(1, 13)]
    by_id = {item["id"]: item for item in questions}
    assert by_id["Q06"]["question"] == "Compara a EMP-0001 con EMP-0004"
    assert by_id["Q06"]["must_include"] == ["Ana López", "Jorge Díaz"]
    assert by_id["Q10"]["must_include"] == ["Jorge Díaz", "Líder técnico"]
    assert by_id["Q10"]["history"][0]["content"] == "Hablemos de EMP-0004"
    digest = json.dumps(questions, sort_keys=True, ensure_ascii=False)
    assert "Q12" in digest


def test_a_model_without_a_verified_price_blocks_the_plan(evaluation, monkeypatch):
    """Un MODEL_SMALL sin precio en la tabla se rechaza antes de cualquier llamada."""
    _set_env(monkeypatch)
    monkeypatch.setenv("MODEL_SMALL", "@cf/meta/llama-3.2-3b-instruct")
    _forbid_run(evaluation, monkeypatch)
    _argv(monkeypatch)
    assert evaluation.main() == 2


def test_input_cap_below_the_minimum_is_rejected_before_anything_runs(
        evaluation, monkeypatch):
    """Un tope de 30 rechazaría toda llamada: se explica y no se ejecuta nada."""
    _set_env(monkeypatch)
    _forbid_run(evaluation, monkeypatch)
    _argv(monkeypatch, "--run", "real", "--max-calls", "96", "--max-usd", "0.05",
          "--max-input-tokens", "30")
    assert evaluation.main() == 2


def test_probe_selection_limits_questions_variants_and_calls(evaluation):
    """La sonda de compatibilidad usa 3 preguntas y 1 variante: máximo 12 llamadas."""
    questions = evaluation._load_questions()  # pylint: disable=protected-access
    chosen, variants = evaluation.select(questions, "Q01,Q04,Q09", "optimized")
    plan = evaluation.build_plan(chosen, variants)
    assert [item["id"] for item in chosen] == ["Q01", "Q04", "Q09"]
    assert plan["max_calls_total"] == 12 and plan["expected_calls_total"] == 9
    with pytest.raises(ValueError):
        evaluation.select(questions, "Q99", "")


def test_protocol_failures_are_counted_separately_from_quality(evaluation):
    """Una salida que rompe el protocolo JSON se distingue de una respuesta errónea."""
    assert evaluation.INVALID_OUTPUT_ANSWER in evaluation.PROTOCOL_FAILURES
    assert evaluation.STEP_LIMIT_ANSWER in evaluation.PROTOCOL_FAILURES


def test_a_provider_error_stops_the_run_without_further_calls(
        evaluation, monkeypatch):
    """Tras el primer estado distinto de 200 no se envían más preguntas."""
    asked = []

    def failing(_client, _key, item):
        asked.append(item["id"])
        return {"calls": 1, "cost_usd": 0.0, "status": 502}

    monkeypatch.setattr(evaluation, "_ask", failing)
    monkeypatch.setattr(evaluation, "TestClient", lambda *_a, **_k: None)
    monkeypatch.setattr(evaluation, "create_app", lambda **_k: None)
    questions = evaluation._load_questions()  # pylint: disable=protected-access
    guard = evaluation._install_guard("fake", 12, 0.01, 3000)  # pylint: disable=protected-access
    rows = evaluation._run_variant(  # pylint: disable=protected-access
        "optimized", "fake", "clave", questions[:3], (guard, 0, 0.0, 12, 0.01))
    assert asked == ["Q01"] and len(rows) == 1


def test_single_question_probe_is_capped_at_one_call(evaluation, monkeypatch):
    """Con un solo paso el revisor no puede actuar: el máximo por pregunta es 1."""
    assert evaluation.max_calls_per_question(3) == 4
    assert evaluation.max_calls_per_question(1) == 1
    monkeypatch.setenv("AGENT_MAX_STEPS", "1")
    questions = evaluation._load_questions()  # pylint: disable=protected-access
    chosen, variants = evaluation.select(questions, "Q09", "optimized")
    plan = evaluation.build_plan(chosen, variants)
    assert plan["max_calls_total"] == 1 and plan["expected_calls_total"] == 1


def test_interrupted_run_keeps_partial_results(evaluation, monkeypatch, tmp_path):
    """Una interrupción a mitad conserva las filas ya obtenidas y marca parcial."""
    shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    original = evaluation._ask  # pylint: disable=protected-access
    seen = []

    def failing(client, api_key, item):
        if len(seen) == 2:
            raise KeyboardInterrupt
        seen.append(item["id"])
        return original(client, api_key, item)

    monkeypatch.setattr(evaluation, "_ask", failing)
    args = SimpleNamespace(run="fake", max_calls=0, max_usd=0.0,
                           max_input_tokens=3000, only="", variants="baseline")
    selection = evaluation.select(evaluation._load_questions(),  # pylint: disable=protected-access
                                  "", "baseline")
    plan = evaluation.build_plan(*selection)
    code = evaluation._execute(args, plan, selection)  # pylint: disable=protected-access
    assert code == 1
    folders = list((tmp_path / "evidence" / "costs").iterdir())
    assert len(folders) == 1
    result = json.loads((folders[0] / "results.json").read_text(encoding="utf-8"))
    assert result["complete"] is False
    assert result["interrupted_by"] == "KeyboardInterrupt"
    assert [row["id"] for row in result["baseline"]["rows"]] == seen
    assert result["baseline"]["summary"]["questions"] == 2
