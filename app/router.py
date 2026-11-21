"""Enrutador por regla: elige el modelo de cada pregunta (palanca 1)."""

from dataclasses import dataclass

from app.config import Config

LARGE_MODEL_KEYWORDS = ("compara", "resume", "explica", "por qué", "analiza", "todos")
REASON_ROUTING_DISABLED = "routing_disabled"
REASON_TOO_LONG = "too_long"
REASON_DEFAULT = "default"
REASON_KEYWORD_PREFIX = "keyword:"


@dataclass(frozen=True)
class RouteDecision:
    """Decisión del enrutador.

    :param model: Nombre del modelo elegido.
    :param reason: Motivo de la elección.
    """

    model: str
    reason: str


def choose_route(question: str, config: Config) -> RouteDecision:
    """Elige el modelo con reglas, sin llamar a otro modelo.

    Va al modelo capaz si el enrutamiento está apagado, si la pregunta supera
    ``router_max_chars`` o si contiene una palabra clave; si no, al barato.

    :param question: Pregunta de la persona usuaria.
    :param config: Configuración con modelos y límites.
    :return: El modelo elegido y el motivo.
    """
    if not config.routing:
        return RouteDecision(config.model_large, REASON_ROUTING_DISABLED)
    if len(question) > config.router_max_chars:
        return RouteDecision(config.model_large, REASON_TOO_LONG)
    lowered = question.casefold()
    for keyword in LARGE_MODEL_KEYWORDS:
        if keyword in lowered:
            return RouteDecision(config.model_large, REASON_KEYWORD_PREFIX + keyword)
    return RouteDecision(config.model_small, REASON_DEFAULT)
