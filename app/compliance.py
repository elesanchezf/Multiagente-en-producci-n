"""Reglas de compliance de producción, como función pura.

Los mensajes nombran la variable afectada y nunca incluyen valores.
"""

from typing import List

from app.auth import MIN_KEY_LENGTH
from app.config import Config

PRODUCTION = "production"


def check_production(config: Config) -> List[str]:
    """Lista las reglas de producción que la configuración incumple.

    :param config: Configuración ya validada.
    :return: Mensajes de las reglas incumplidas; vacía si todo cumple o si
        el entorno no es ``production``.
    """
    if config.environment != PRODUCTION:
        return []
    violations: List[str] = []
    if config.model_provider == "fake":
        violations.append("MODEL_PROVIDER must not be fake in production")
    if not config.api_keys:
        violations.append("API_KEYS must not be empty in production")
    elif any(len(key) < MIN_KEY_LENGTH for key in config.api_keys.values()):
        violations.append(
            f"API_KEYS must have keys of at least {MIN_KEY_LENGTH} characters"
        )
    if config.langsmith_tracing and not config.hide_inputs:
        violations.append("HIDE_INPUTS must be true when tracing is on")
    if config.langsmith_tracing and not config.hide_outputs:
        violations.append("HIDE_OUTPUTS must be true when tracing is on")
    return violations
