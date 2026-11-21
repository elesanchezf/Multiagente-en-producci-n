"""Configuración del servicio a partir de variables de entorno."""

import os
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional

from app.auth import parse_api_keys
from app.errors import ConfigError

ENVIRONMENTS = ("development", "production")
DEFAULT_ENVIRONMENT = "development"
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
SUPPORTED_PROVIDERS = ("fake", "gateway")
REQUIRED_GATEWAY_VARIABLES = ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN")
DEFAULT_MODEL_SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
DEFAULT_MODEL_LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
DEFAULT_ROUTER_MAX_CHARS = 80
DEFAULT_HISTORY_WINDOW = 6
DEFAULT_MODEL_MAX_TOKENS = 300
DEFAULT_MODEL_TEMPERATURE = 0.0
DEFAULT_PRICES_PATH = "data/model_prices.json"
DEFAULT_GATEWAY_ID = "default"
DEFAULT_PROVIDER = "fake"
DEFAULT_MAX_STEPS = 3
DEFAULT_MAX_QUESTION_CHARS = 2000
DEFAULT_EMPLOYEES_PATH = "data/employees.json"
DEFAULT_SERVICE_NAME = "hr-assistant"
DEFAULT_SLO_P95_MS = 2000


__all__ = ["Config", "ConfigError", "load_config"]


@dataclass(frozen=True)
class _CoreSettings:
    """Parámetros base del servicio.

    :param model_provider: Nombre del proveedor de modelo.
    :param agent_max_steps: Tope de vueltas del bucle del agente.
    :param max_question_chars: Largo máximo de la pregunta.
    :param employees_path: Ruta del archivo de empleados.
    """

    model_provider: str = DEFAULT_PROVIDER
    agent_max_steps: int = DEFAULT_MAX_STEPS
    max_question_chars: int = DEFAULT_MAX_QUESTION_CHARS
    employees_path: str = DEFAULT_EMPLOYEES_PATH


@dataclass(frozen=True)
class _LogSettings(_CoreSettings):
    """Parámetros del log y de la meta de latencia.

    :param service_name: Valor del campo ``service`` del log.
    :param slo_p95_ms: Meta de latencia p95 en milisegundos.
    """

    service_name: str = DEFAULT_SERVICE_NAME
    slo_p95_ms: int = DEFAULT_SLO_P95_MS


@dataclass(frozen=True)
class _CallSettings(_LogSettings):
    """Parámetros de cada llamada al modelo.

    :param model_max_tokens: Tope de tokens de salida.
    :param model_temperature: Temperatura de muestreo.
    :param cache_ttl_seconds: Vigencia de la caché del gateway (0: apagada).
    """

    model_max_tokens: int = DEFAULT_MODEL_MAX_TOKENS
    model_temperature: float = DEFAULT_MODEL_TEMPERATURE
    cache_ttl_seconds: int = 0


@dataclass(frozen=True)
class _LeverSettings(_CallSettings):
    """Parámetros del enrutamiento y de la ventana de historial.

    :param model_small: Modelo barato.
    :param model_large: Modelo capaz.
    :param routing: Enciende el enrutamiento por pregunta.
    :param router_max_chars: Largo desde el cual se usa el modelo capaz.
    :param history_window: Mensajes de historial que se mandan al modelo.
    """

    model_small: str = DEFAULT_MODEL_SMALL
    model_large: str = DEFAULT_MODEL_LARGE
    routing: bool = True
    router_max_chars: int = DEFAULT_ROUTER_MAX_CHARS
    history_window: int = DEFAULT_HISTORY_WINDOW


@dataclass(frozen=True)
class _GatewaySettings(_LeverSettings):
    """Parámetros de precios y de Cloudflare.

    :param prices_path: Ruta de la tabla de precios.
    :param cf_account_id: Cuenta de Cloudflare.
    :param cf_gateway_id: Gateway de Cloudflare.
    :param cf_api_token: Token de Cloudflare (secreto, fuera de ``repr``).
    :param cf_aig_token: Token de AI Gateway autenticado (opcional, secreto,
        fuera de ``repr``); si está vacío no se envía el encabezado.
    """

    prices_path: str = DEFAULT_PRICES_PATH
    cf_account_id: str = ""
    cf_gateway_id: str = DEFAULT_GATEWAY_ID
    cf_api_token: str = field(default="", repr=False)
    cf_aig_token: str = field(default="", repr=False)


@dataclass(frozen=True)
class Config(_GatewaySettings):
    """Configuración inmutable del servicio.

    Hereda los parámetros base, de log, de palancas de costo y de Cloudflare.

    :param langsmith_tracing: Enciende las trazas de LangSmith.
    :param hide_inputs: No enviar entradas a LangSmith.
    :param hide_outputs: No enviar salidas a LangSmith.
    :param environment: ``development`` o ``production``.
    :param api_keys: Cliente a clave (secreto, fuera de ``repr``).
    :param rate_limit_per_minute: Peticiones por cliente por minuto.
    """

    langsmith_tracing: bool = False
    hide_inputs: bool = True
    hide_outputs: bool = True
    environment: str = DEFAULT_ENVIRONMENT
    api_keys: Dict[str, str] = field(default_factory=dict, repr=False, compare=False)
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE


def _boolean(env: Mapping[str, str], name: str, default: bool) -> bool:
    """Lee un booleano de las variables de entorno.

    :param env: Variables de entorno.
    :param name: Nombre de la variable.
    :param default: Valor por omisión.
    :return: El booleano validado.
    :raises ConfigError: Si el valor no es ``true`` ni ``false``.
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value not in ("true", "false"):
        raise ConfigError(f"{name} must be true or false, got {raw!r}")
    return value == "true"


def _bounded_int(
    env: Mapping[str, str], name: str, default: int, minimum: int
) -> int:
    """Lee un entero con un mínimo de las variables de entorno.

    :param env: Variables de entorno.
    :param name: Nombre de la variable.
    :param default: Valor por omisión.
    :param minimum: Valor mínimo permitido.
    :return: El entero validado.
    :raises ConfigError: Si el valor no es entero o es menor que el mínimo.
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from error
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return value


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Lee un entero positivo de las variables de entorno.

    :param env: Variables de entorno.
    :param name: Nombre de la variable.
    :param default: Valor por omisión.
    :return: El entero validado.
    :raises ConfigError: Si el valor no es un entero mayor que cero.
    """
    return _bounded_int(env, name, default, 1)


def _non_negative_float(env: Mapping[str, str], name: str, default: float) -> float:
    """Lee un número no negativo de las variables de entorno.

    :param env: Variables de entorno.
    :param name: Nombre de la variable.
    :param default: Valor por omisión.
    :return: El número validado.
    :raises ConfigError: Si el valor no es un número finito mayor o igual a cero.
    """
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from error
    if not 0 <= value < float("inf"):
        raise ConfigError(f"{name} must be zero or greater, got {raw!r}")
    return value


def _check_gateway(values: Mapping[str, str]) -> None:
    """Exige las variables de Cloudflare cuando el proveedor es ``gateway``.

    :param values: Valores de las variables ``CF_*`` ya resueltos.
    :raises ConfigError: Si falta alguna; el mensaje solo nombra la variable.
    """
    for name in REQUIRED_GATEWAY_VARIABLES:
        if not values[name].strip():
            raise ConfigError(f"{name} is required when MODEL_PROVIDER=gateway")


def _environment(env: Mapping[str, str]) -> str:
    """Lee ``ENVIRONMENT`` y valida que sea un entorno conocido.

    :param env: Variables de entorno.
    :return: ``development`` (por omisión) o ``production``.
    :raises ConfigError: Si el valor es otro.
    """
    value = (env.get("ENVIRONMENT") or DEFAULT_ENVIRONMENT).strip().lower()
    if value not in ENVIRONMENTS:
        raise ConfigError(f"ENVIRONMENT must be one of {ENVIRONMENTS}")
    return value


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    """Construye la configuración validando cada valor.

    :param env: Variables de entorno; si es ``None`` se usa ``os.environ``.
    :return: La configuración validada.
    :raises ConfigError: Si algún valor es inválido.
    """
    env = os.environ if env is None else env
    provider = env.get("MODEL_PROVIDER") or DEFAULT_PROVIDER
    if provider not in SUPPORTED_PROVIDERS:
        raise ConfigError(
            f"MODEL_PROVIDER must be one of {SUPPORTED_PROVIDERS}, got {provider!r}"
        )
    cloudflare = {
        "CF_ACCOUNT_ID": env.get("CF_ACCOUNT_ID") or "",
        "CF_GATEWAY_ID": env.get("CF_GATEWAY_ID") or DEFAULT_GATEWAY_ID,
        "CF_API_TOKEN": env.get("CF_API_TOKEN") or "",
    }
    if provider == "gateway":
        _check_gateway(cloudflare)
    return Config(
        model_provider=provider,
        model_small=env.get("MODEL_SMALL") or DEFAULT_MODEL_SMALL,
        model_large=env.get("MODEL_LARGE") or DEFAULT_MODEL_LARGE,
        routing=_boolean(env, "ROUTING", True),
        router_max_chars=_positive_int(
            env, "ROUTER_MAX_CHARS", DEFAULT_ROUTER_MAX_CHARS
        ),
        history_window=_bounded_int(
            env, "HISTORY_WINDOW", DEFAULT_HISTORY_WINDOW, 0
        ),
        model_max_tokens=_positive_int(
            env, "MODEL_MAX_TOKENS", DEFAULT_MODEL_MAX_TOKENS
        ),
        model_temperature=_non_negative_float(
            env, "MODEL_TEMPERATURE", DEFAULT_MODEL_TEMPERATURE
        ),
        cache_ttl_seconds=_bounded_int(env, "CACHE_TTL_SECONDS", 0, 0),
        prices_path=env.get("PRICES_PATH") or DEFAULT_PRICES_PATH,
        cf_account_id=cloudflare["CF_ACCOUNT_ID"],
        cf_gateway_id=cloudflare["CF_GATEWAY_ID"],
        cf_api_token=cloudflare["CF_API_TOKEN"],
        cf_aig_token=env.get("CF_AIG_TOKEN") or "",
        agent_max_steps=_positive_int(env, "AGENT_MAX_STEPS", DEFAULT_MAX_STEPS),
        max_question_chars=_positive_int(
            env, "MAX_QUESTION_CHARS", DEFAULT_MAX_QUESTION_CHARS
        ),
        employees_path=env.get("EMPLOYEES_PATH") or DEFAULT_EMPLOYEES_PATH,
        service_name=env.get("SERVICE_NAME") or DEFAULT_SERVICE_NAME,
        slo_p95_ms=_positive_int(env, "SLO_P95_MS", DEFAULT_SLO_P95_MS),
        langsmith_tracing=_boolean(env, "LANGSMITH_TRACING", False),
        hide_inputs=_boolean(env, "HIDE_INPUTS", True),
        hide_outputs=_boolean(env, "HIDE_OUTPUTS", True),
        environment=_environment(env),
        api_keys=parse_api_keys(env.get("API_KEYS") or ""),
        rate_limit_per_minute=_positive_int(
            env, "RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
    )
