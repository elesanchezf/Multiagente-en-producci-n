"""Interfaz del modelo y modelo simulado determinista."""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from app.config import Config, ConfigError
from app.directory import EmployeeDirectory

TOOL_RESULT_PREFIX = "Resultado de la herramienta: "
GUIDANCE_ANSWER = "Pregúntame por un empleado (EMP-0001) o un departamento."
EMPLOYEE_ID_PATTERN = re.compile(r"EMP-\d{4}")


@dataclass(frozen=True)
class ModelResponse:
    """Respuesta de un modelo.

    :param text: Texto devuelto (un objeto JSON según el protocolo).
    :param input_tokens: Tokens de entrada (aproximados en el modelo simulado).
    :param output_tokens: Tokens de salida (aproximados en el modelo simulado).
    :param cached: Verdadero si la caché del gateway respondió la llamada.
    """

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool = False


class ModelUnavailable(Exception):
    """El modelo no pudo responder; el mensaje nunca incluye credenciales.

    :param message: Descripción del fallo, sin datos sensibles.
    :param status_code: Estado HTTP de la respuesta de error, si hubo una.
    """

    def __init__(self, message: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# Interfaz de un solo método: el agente solo necesita ``complete``.
# pylint: disable-next=too-few-public-methods
class Model(Protocol):
    """Interfaz que cumple cualquier modelo usable por el agente."""

    def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Devuelve la siguiente respuesta de la conversación.

        :param messages: Mensajes con ``role`` y ``content``.
        :return: La respuesta del modelo.
        """


def count_words(text: str) -> int:
    """Cuenta palabras como aproximación de tokens.

    :param text: Texto a medir.
    :return: Número de palabras.
    """
    return len(text.split())


# Proveedor simulado: cumple la interfaz ``Model``, de un solo método.
# pylint: disable-next=too-few-public-methods
class FakeModel:
    """Modelo simulado: decide con reglas sobre el último mensaje.

    :param directory: Directorio usado para reconocer departamentos.
    :param name: Nombre del modelo simulado; fija el precio que se le aplica.
    """

    def __init__(self, directory: EmployeeDirectory, name: str = "fake"):
        self._directory = directory
        self.name = name

    def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Aplica las reglas del modelo simulado.

        :param messages: Mensajes de la conversación.
        :return: Respuesta JSON con conteo aproximado de tokens.
        """
        last = messages[-1]["content"] if messages else ""
        text = json.dumps(self._decide(last), ensure_ascii=False)
        input_tokens = sum(count_words(m["content"]) for m in messages)
        return ModelResponse(text, input_tokens, count_words(text))

    def _decide(self, last: str) -> Dict:
        """Elige la acción según las cuatro reglas en orden.

        :param last: Contenido del último mensaje.
        :return: Objeto del protocolo (herramienta o respuesta).
        """
        if last.startswith(TOOL_RESULT_PREFIX):
            result = last[len(TOOL_RESULT_PREFIX):]
            return {"answer": f"Según el directorio: {result}"}
        match = EMPLOYEE_ID_PATTERN.search(last)
        if match:
            return {"tool": "get_employee", "args": {"employee_id": match.group()}}
        lowered = last.casefold()
        for department in self._directory.departments:
            if department.casefold() in lowered:
                return {
                    "tool": "search_by_department",
                    "args": {"department": department},
                }
        return {"answer": GUIDANCE_ANSWER}


def build_model(config: Config, directory: EmployeeDirectory) -> Model:
    """Selecciona el modelo simulado según ``MODEL_PROVIDER``.

    El proveedor ``gateway`` se arma en :func:`app.models.build_models`.

    :param config: Configuración del servicio.
    :param directory: Directorio de empleados.
    :return: El modelo simulado.
    :raises ConfigError: Si el proveedor no es simulado.
    """
    if config.model_provider == "fake":
        return FakeModel(directory)
    raise ConfigError(f"Unknown model provider: {config.model_provider!r}")
