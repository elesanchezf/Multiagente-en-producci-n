"""API web sin estado del HR Assistant."""

import os
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from app.agent import RunSettings
from app.multiagent import Coordinator
from app.clock import Clock, SystemClock
from app.auth import HEADER_NAME, INVALID_KEY_DETAIL, identify_client
from app.compliance import check_production
from app.config import Config, ConfigError, load_config
from app.directory import EmployeeDirectory
from app.llm import Model, ModelUnavailable
from app.metrics import Metrics
from app.models import build_models
from app.observability import (
    JsonLogger,
    client_var,
    request_id_var,
    resolve_request_id,
)
from app.pricing import Pricing, PricingError
from app.privacy import SensitiveDataError, sensitive_kinds
from app.ratelimit import RateLimiter
from app.router import choose_route
from app.tracing import is_tracing_enabled, traced

STATIC_DIR = Path(__file__).resolve().parent / "static"
PROTECTED_PATHS = ("/ask", "/metrics")
MAX_HISTORY_ITEMS = 50
MAX_HISTORY_CONTENT_CHARS = 10000


class HistoryItem(BaseModel):
    """Mensaje previo de la conversación enviado por el cliente."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_HISTORY_CONTENT_CHARS)


class AskRequest(BaseModel):
    """Cuerpo de ``POST /ask``."""

    question: str = Field(min_length=1)
    history: Optional[List[HistoryItem]] = Field(
        default=None, max_length=MAX_HISTORY_ITEMS
    )


def _agent_factory(
    config: Config,
    directory: EmployeeDirectory,
    model: Optional[Model],
    logger: JsonLogger,
) -> Callable[[str], Coordinator]:
    """Prepara modelos, precios y trazas, y devuelve el armador de agentes.

    :param config: Configuración del servicio.
    :param directory: Directorio de empleados.
    :param model: Modelo único para ambas rutas, o ``None`` para armarlos.
    :param logger: Emisor de eventos.
    :return: Función que, dada una pregunta, arma el agente con el modelo
        elegido por el enrutador.
    :raises PricingError: Si algún modelo no tiene precio.
    """
    models = (
        {config.model_small: model, config.model_large: model}
        if model is not None
        else build_models(config, directory)
    )
    pricing = Pricing.from_file(config.prices_path)
    for name in models:
        if not pricing.has_model(name):
            raise PricingError(f"No price for model {name!r}")
    enabled = config.langsmith_tracing and is_tracing_enabled(
        {**os.environ, "LANGSMITH_TRACING": "true"}
    )

    def trace(name: str):
        """Crea el decorador de traza con las reglas de ocultamiento.

        :param name: Nombre de la traza.
        :return: El decorador.
        """
        return traced(
            name,
            enabled,
            config.hide_inputs,
            config.hide_outputs,
            request_id_var.get,
            client_var.get,
        )

    def agent_for(question: str) -> Coordinator:
        """Elige el modelo de la pregunta y arma el agente que lo usa.

        :param question: Pregunta de la persona usuaria.
        :return: Agente con el modelo, el precio y la ventana de esa pregunta.
        """
        decision = choose_route(question, config)
        settings = RunSettings(
            decision.model, decision.reason, config.history_window, pricing
        )
        return Coordinator(
            models[decision.model],
            directory,
            config.agent_max_steps,
            logger,
            trace,
            settings,
        )

    return agent_for


def _payload(result, request_id: str) -> dict:
    """Arma el cuerpo de respuesta de ``POST /ask``.

    :param result: Resultado del coordinador.
    :param request_id: Identificador de la petición.
    :return: Diccionario serializable.
    """
    return {
        "request_id": request_id,
        "answer": result.answer,
        "steps": result.steps,
        "tools_used": result.tools_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "model": result.model,
        "route": result.route,
        "cached_calls": result.cached_calls,
        "cost_usd": result.cost_usd,
        "agents_used": result.agents_used,
        "review_status": result.review_status,
        "review_calls": result.review_calls,
        "review_input_tokens": result.review_input_tokens,
        "review_output_tokens": result.review_output_tokens,
        "review_cost_usd": result.review_cost_usd,
    }


def _enforce_compliance(config: Config) -> None:
    """Detiene el arranque si la configuración incumple las reglas de producción.

    :param config: Configuración del servicio.
    :raises ConfigError: Si hay incumplimientos.
    """
    violations = check_production(config)
    if violations:
        raise ConfigError("Production compliance failed: " + "; ".join(violations))


def _error_details(error: ModelUnavailable) -> dict:
    """Campos seguros del log para un fallo del proveedor.

    :param error: Fallo del modelo.
    :return: Tipo de error, motivo (mensaje sin datos sensibles) y, si existe,
        código HTTP.
    """
    details = {"error_type": type(error).__name__, "reason": str(error)}
    if error.status_code is not None:
        details["status_code"] = error.status_code
    return details


def _make_gate(
    api_keys: Dict[str, str], limiter: RateLimiter
) -> Callable[[Request], Optional[JSONResponse]]:
    """Crea la verificación de clave y de límite de las rutas protegidas.

    Seguridad: los intentos con clave inválida NO tienen límite por origen;
    solo el cliente autenticado tiene límite de peticiones. La clave se compara
    en ``auth.identify_client`` y nunca se registra.

    :param api_keys: Diccionario de cliente a clave.
    :param limiter: Limitador de peticiones por cliente.
    :return: Función que, dada la petición, devuelve la respuesta ``401`` o
        ``429``, o ``None`` si puede seguir.
    """

    def gate(request: Request) -> Optional[JSONResponse]:
        """Exige clave y aplica el límite en las rutas protegidas.

        :param request: Petición entrante.
        :return: La respuesta de rechazo, o ``None`` si puede seguir.
        """
        if request.url.path not in PROTECTED_PATHS:
            return None
        client = identify_client(api_keys, request.headers.get(HEADER_NAME))
        if client is None:
            return JSONResponse(
                status_code=401, content={"detail": INVALID_KEY_DETAIL}
            )
        client_var.set(client)
        decision = limiter.check(client)
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(decision.retry_after)},
            )
        return None

    return gate


def create_app(
    config: Optional[Config] = None,
    model: Optional[Model] = None,
    directory: Optional[EmployeeDirectory] = None,
    clock: Optional[Clock] = None,
) -> FastAPI:
    """Construye la aplicación con sus dependencias inyectables.

    :param config: Configuración; si es ``None`` se lee del entorno.
    :param model: Modelo único para ambas rutas; si es ``None`` se arman los
        modelos barato y capaz según la configuración.
    :param directory: Directorio; si es ``None`` se carga del archivo.
    :param clock: Reloj; si es ``None`` se usa el reloj del sistema.
    :return: La aplicación FastAPI.
    """
    config = config or load_config()
    _enforce_compliance(config)
    clock = clock or SystemClock()
    directory = directory or EmployeeDirectory.from_file(config.employees_path)
    logger = JsonLogger(config.service_name, clock)
    metrics = Metrics(config.slo_p95_ms)
    gate = _make_gate(config.api_keys, RateLimiter(config.rate_limit_per_minute, clock))
    agent_for = _agent_factory(config, directory, model, logger)

    api = FastAPI(title="HR Assistant")

    @api.exception_handler(RequestValidationError)
    async def invalid_body(_request, _error):
        """Evita que los errores de validación devuelvan valores de entrada."""
        logger.emit("security", action="invalid_request")
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @api.middleware("http")
    async def observe(request: Request, call_next):
        """Asigna ``request_id``, autentica, mide la petición y atiende fallos."""
        request_id = resolve_request_id(request.headers.get("X-Request-ID"))
        token = request_id_var.set(request_id)
        client_token = client_var.set(None)
        started = clock.now()
        try:
            try:
                response = gate(request) or await call_next(request)
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.emit("error", error_type=type(error).__name__)
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "internal error", "request_id": request_id},
                )
            response.headers["X-Request-ID"] = request_id
            elapsed = (clock.now() - started).total_seconds() * 1000
            latency_ms = int(round(elapsed))
            logger.emit(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=latency_ms,
            )
            metrics.record_request(latency_ms, error=response.status_code >= 500)
            return response
        finally:
            client_var.reset(client_token)
            request_id_var.reset(token)

    @api.get("/metrics")
    def metrics_endpoint() -> dict:
        """Devuelve las métricas de este proceso."""
        return metrics.snapshot()

    @api.get("/", include_in_schema=False)
    def home() -> FileResponse:
        """Sirve la página web."""
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @api.get("/health")
    def health() -> dict:
        """Indica que el servicio está vivo."""
        return {"status": "ok", "pid": os.getpid()}

    @api.post("/ask")
    def ask(body: AskRequest) -> dict:
        """Responde una pregunta sin guardar estado."""
        if not body.question.strip() or len(body.question) > config.max_question_chars:
            raise HTTPException(status_code=422, detail="Invalid question length")
        history = [item.model_dump() for item in body.history or []]
        kinds = sensitive_kinds([body.question, history])
        if kinds:
            logger.emit("security", action="input_blocked", categories=sorted(kinds))
            raise HTTPException(status_code=422, detail="Sensitive information blocked")
        try:
            result = agent_for(body.question).run(body.question, history)
            output_kinds = sensitive_kinds(result.answer)
            if output_kinds:
                raise SensitiveDataError("final_output", output_kinds)
        except SensitiveDataError as error:
            logger.emit("security", action="output_blocked", stage=error.stage,
                        categories=error.kinds)
            return JSONResponse(status_code=502, content={
                "detail": "Sensitive information blocked",
                "request_id": request_id_var.get(),
            })
        except ModelUnavailable as error:
            logger.emit("error", **_error_details(error))
            return JSONResponse(
                status_code=502,
                content={
                    "detail": "model unavailable",
                    "request_id": request_id_var.get(),
                },
            )
        metrics.record_tokens(result.input_tokens, result.output_tokens)
        metrics.record_cost(result.cost_usd)
        return _payload(result, request_id_var.get())

    return api


def validate_environment() -> Config:
    """Valida la configuración del entorno y las reglas de producción.

    No lee archivos de datos. Los mensajes de error nunca incluyen el valor
    de una clave.

    :return: La configuración validada.
    :raises ConfigError: Si la configuración es inválida o incumple compliance.
    """
    config = load_config()
    _enforce_compliance(config)
    return config


# Falla al importar si la configuración es inválida o incumple compliance.
validate_environment()


def __getattr__(name: str):
    """Crea ``app`` de forma perezosa para no leer datos al importar.

    :param name: Atributo solicitado.
    :return: La aplicación por omisión cuando se pide ``app``.
    :raises AttributeError: Si el atributo no existe.
    """
    if name == "app":
        instance = create_app()
        globals()["app"] = instance
        return instance
    raise AttributeError(name)
