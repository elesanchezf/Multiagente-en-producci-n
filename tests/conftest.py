"""Fixtures compartidas de las pruebas del HR Assistant.

Supuestos de interfaz que el desarrollador debe respetar (la spec no fija
los nombres internos; se documentan aqui para que las pruebas sean claras):

- ``app.config``: ``Config`` (campos ``model_provider``, ``agent_max_steps``,
  ``max_question_chars``, ``employees_path``), ``load_config(env)`` y
  ``ConfigError``.
- ``app.directory``: ``EmployeeDirectory(employees)``, ``from_file(path)``,
  ``get_employee(id)`` (``None`` si no existe), ``search_by_department(name)``
  (lista) y ``DirectoryError``.
- ``app.llm``: ``ModelResponse(text, input_tokens, output_tokens)``,
  ``FakeModel(directory)`` con ``complete(messages)`` y ``build_model``.
- ``app.agent``: ``Agent(model, directory, max_steps)``, ``run(question,
  history=None)`` que devuelve un objeto con ``answer``, ``steps``,
  ``tools_used``, ``input_tokens`` y ``output_tokens``, y la constante
  ``STEP_LIMIT_ANSWER``.
- ``app.main``: ``create_app(config=None, model=None, directory=None)``.

Todos los datos son ficticios.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.directory import EmployeeDirectory
from app.main import create_app

DEMO_EMPLOYEES = [
    {
        "id": "EMP-0001",
        "name": "Ana López",
        "department": "Tecnología",
        "role": "Analista de datos",
        "start_date": "2019-03-04",
        "status": "activo",
    },
    {
        "id": "EMP-0004",
        "name": "Jorge Díaz",
        "department": "Tecnología",
        "role": "Líder técnico",
        "start_date": "2022-01-10",
        "status": "activo",
    },
    {
        "id": "EMP-0005",
        "name": "Sofía Gómez",
        "department": "Finanzas",
        "role": "Contadora",
        "start_date": "2020-05-25",
        "status": "activo",
    },
]


@pytest.fixture(name="employees_path")
def employees_path_fixture(tmp_path):
    """Escribe un directorio ficticio en un archivo temporal."""
    path = tmp_path / "employees.json"
    path.write_text(json.dumps(DEMO_EMPLOYEES), encoding="utf-8")
    return path


@pytest.fixture
def directory(employees_path):
    """Directorio cargado con los datos ficticios."""
    return EmployeeDirectory.from_file(employees_path)


CLIENT_KEYS = {
    "acme": "fake-key-acme-0000000000",
    "globex": "fake-key-globex-000000000",
}
API_KEYS_VALUE = ",".join(f"{name}:{key}" for name, key in CLIENT_KEYS.items())
HIGH_LIMIT = "1000"


@pytest.fixture
def client_keys():
    """Claves ficticias por cliente (sesion 4)."""
    return dict(CLIENT_KEYS)


@pytest.fixture
def manual_clock():
    """Reloj que solo avanza cuando la prueba lo pide (sesion 4).

    Tiene ``now()`` (UTC) y ``advance(seconds)``.
    """

    class ManualClock:
        """Reloj controlado por la prueba."""

        def __init__(self):
            self._instant = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        def now(self):
            """Devuelve el instante actual."""
            return self._instant

        def advance(self, seconds):
            """Avanza el reloj la cantidad de segundos indicada."""
            self._instant += timedelta(seconds=seconds)

    return ManualClock()


@pytest.fixture(name="make_secure_client")
def make_secure_client_fixture(employees_path):
    """Fabrica clientes SIN clave por omision, para probar el acceso (sesion 4).

    Supuestos de interfaz de la sesion 4:

    - ``load_config(env)`` lee ``ENVIRONMENT`` (por omision ``development``),
      ``API_KEYS`` y ``RATE_LIMIT_PER_MINUTE`` (por omision 30). ``Config``
      expone ``environment``, ``api_keys`` (``dict`` cliente a clave, fuera de
      ``repr``) y ``rate_limit_per_minute``.
    - Una ``API_KEYS`` mal formada o una ``RATE_LIMIT_PER_MINUTE`` invalida
      hace fallar ``load_config`` con ``ConfigError``.
    - ``create_app`` ejecuta las reglas de compliance y lanza ``ConfigError``
      (o una subclase) si ``ENVIRONMENT=production`` las incumple.
    - Una variable con valor ``None`` en ``overrides`` se quita del entorno.
    """

    def _make(clock=None, model=None, **overrides):
        env = {
            "MODEL_PROVIDER": "fake",
            "EMPLOYEES_PATH": str(employees_path),
            "API_KEYS": API_KEYS_VALUE,
            "RATE_LIMIT_PER_MINUTE": HIGH_LIMIT,
        }
        env.update(overrides)
        env = {name: value for name, value in env.items() if value is not None}
        app = create_app(config=load_config(env), model=model, clock=clock)
        return TestClient(app, raise_server_exceptions=False)

    return _make


def _with_key(client):
    """Agrega la clave ficticia del cliente ``acme`` a todas sus peticiones."""
    client.headers["X-API-Key"] = CLIENT_KEYS["acme"]
    return client


@pytest.fixture
def make_client(make_secure_client):
    """Fabrica clientes HTTP autenticados con ``create_app`` (sesion 1)."""

    def _make(max_steps=3, max_chars=2000):
        client = make_secure_client(
            AGENT_MAX_STEPS=str(max_steps), MAX_QUESTION_CHARS=str(max_chars)
        )
        return _with_key(client)

    return _make


@pytest.fixture
def make_observed_client(make_secure_client):
    """Fabrica clientes autenticados con reloj y modelo inyectados (sesion 2).

    Supuestos de interfaz de la sesion 2:

    - ``Config`` agrega ``service_name``, ``slo_p95_ms``, ``langsmith_tracing``,
      ``hide_inputs`` y ``hide_outputs``.
    - ``create_app(config, model, directory, clock)``: el reloj se inyecta.
    - ``app.clock``: ``FixedClock(instant)`` y ``SteppingClock(start, step_seconds)``
      (cada ``now()`` avanza el reloj), ambos con ``now()`` en UTC.
    - El log se escribe en ``sys.stdout`` leido al momento de emitir.
    """

    def _make(clock=None, model=None, slo_p95_ms=2000, tracing=False):
        client = make_secure_client(
            clock=clock,
            model=model,
            SERVICE_NAME="hr-assistant",
            SLO_P95_MS=str(slo_p95_ms),
            LANGSMITH_TRACING="true" if tracing else "false",
        )
        return _with_key(client)

    return _make


TEST_PRICES = {
    "currency": "USD",
    "unit": "per million tokens",
    "models": {
        "small-test": {"input": 1000.0, "output": 2000.0},
        "large-test": {"input": 10000.0, "output": 20000.0},
    },
}


@pytest.fixture(name="prices_path")
def prices_path_fixture(tmp_path):
    """Escribe una tabla de precios ficticia en un archivo temporal."""
    path = tmp_path / "model_prices.json"
    path.write_text(json.dumps(TEST_PRICES), encoding="utf-8")
    return path


@pytest.fixture(name="cost_env")
def cost_env_fixture(employees_path, prices_path):
    """Variables de entorno minimas para el modelo simulado de la sesion 3."""
    return {
        "MODEL_PROVIDER": "fake",
        "EMPLOYEES_PATH": str(employees_path),
        "PRICES_PATH": str(prices_path),
        "MODEL_SMALL": "small-test",
        "MODEL_LARGE": "large-test",
    }


@pytest.fixture
def make_cost_client(cost_env):
    """Fabrica clientes con las palancas de costo (sesion 3).

    Supuestos de interfaz de la sesion 3:

    - ``load_config(env)`` lee ``MODEL_SMALL``, ``MODEL_LARGE``, ``ROUTING``,
      ``ROUTER_MAX_CHARS``, ``HISTORY_WINDOW``, ``MODEL_MAX_TOKENS``,
      ``MODEL_TEMPERATURE``, ``CACHE_TTL_SECONDS``, ``PRICES_PATH`` y las
      tres ``CF_*``. Los atributos de ``Config`` son esos nombres en
      minusculas (``model_small``, ``cf_api_token``, etc.).
    - Si ``create_app`` recibe ``model``, ese objeto atiende tanto la ruta
      pequena como la grande; el precio se toma del nombre elegido.
    - ``ModelResponse(text, input_tokens, output_tokens, cached=False)``.
    """

    def _make(model=None, **overrides):
        env = {
            **cost_env,
            "API_KEYS": API_KEYS_VALUE,
            "RATE_LIMIT_PER_MINUTE": HIGH_LIMIT,
            **overrides,
        }
        app = create_app(config=load_config(env), model=model)
        return _with_key(TestClient(app, raise_server_exceptions=False))

    return _make
