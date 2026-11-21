"""Pruebas de los archivos de entrega: se leen como texto (sesion 4).

No se ejecuta Docker, CI ni Render: se comprueba que los archivos digan lo
que pide la especificacion y que no lleven secretos.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = ("style", "unit", "e2e", "docker")


def _text(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_the_container_runs_as_a_normal_user_and_leaves_secrets_out():
    """El Dockerfile usa un usuario no root y el .dockerignore excluye secretos."""
    dockerfile = _text("Dockerfile")
    assert "FROM python:3.12-slim" in dockerfile
    assert re.search(r"^USER\s+(?!root\b)\S+", dockerfile, re.MULTILINE)
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}" in dockerfile
    ignored = _text(".dockerignore").split()
    for entry in (".env", "tests", "e2e"):
        assert any(line.strip("/") == entry for line in ignored), entry
    assert any("__pycache__" in line for line in ignored)


def test_the_pipeline_chains_four_jobs_on_push_and_pull_request():
    """El flujo de CI encadena cuatro trabajos y corre en push y pull request."""
    workflow = _text(".github/workflows/ci.yml")
    assert "push" in workflow and "pull_request" in workflow
    for job in JOBS:
        assert re.search(rf"^  {job}:", workflow, re.MULTILINE), job
    assert workflow.count("needs:") == 3
    assert re.search(r"max-line-length[= ]88", workflow)
    assert "--cov-fail-under=80" in workflow
    assert "docker build" in workflow


def test_the_render_blueprint_publishes_only_when_checks_pass():
    """El blueprint de Render publica solo tras las verificaciones y sin secretos."""
    blueprint = _text("render.yaml")
    for line in (
        "runtime: docker",
        "plan: free",
        "healthCheckPath: /health",
        "autoDeployTrigger: checksPass",
    ):
        assert line in blueprint
    assert re.search(r"key: ENVIRONMENT\s+value: production", blueprint)
    assert re.search(r"key: MODEL_PROVIDER\s+value: gateway", blueprint)
    for secret in ("API_KEYS", "CF_ACCOUNT_ID", "CF_API_TOKEN", "CF_AIG_TOKEN"):
        assert re.search(rf"key: {secret}\s+sync: false", blueprint), secret
    assert "LANGSMITH_API_KEY" not in blueprint
    assert "value: fake" not in blueprint


def test_the_example_environment_file_lists_the_aig_token_without_a_value():
    """El archivo de ejemplo de entorno declara CF_AIG_TOKEN y lo deja vacio."""
    example = _text(".env.example")
    assert re.search(r"^CF_AIG_TOKEN=[ \t]*$", example, re.MULTILINE)


def test_the_compliance_checklist_is_a_three_column_table_of_the_rules():
    """La lista de compliance es una tabla de tres columnas con las reglas."""
    checklist = _text("doc/compliance-checklist.md")
    rows = [line for line in checklist.splitlines() if line.startswith("|")]
    assert len(rows) >= 5
    assert all(line.count("|") == 4 for line in rows)
    for variable in ("MODEL_PROVIDER", "API_KEYS", "HIDE_INPUTS", "HIDE_OUTPUTS"):
        assert variable in checklist
