"""Agente con bucle acotado que usa herramientas de solo lectura."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.directory import EmployeeDirectory
from app.llm import TOOL_RESULT_PREFIX, Model
from app.pricing import Pricing

STEP_LIMIT_ANSWER = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)
INVALID_OUTPUT_ANSWER = "No pude interpretar la respuesta del modelo."
UNKNOWN_TOOL_ANSWER = "El modelo pidió una herramienta que no existe."
MISSING_ARGS_ANSWER = "El modelo pidió una herramienta sin los argumentos necesarios."


@dataclass
class AgentResult:  # pylint: disable=too-many-instance-attributes
    """Resultado de una ejecución del agente.

    :param answer: Respuesta final.
    :param steps: Vueltas del bucle realizadas.
    :param tools_used: Nombres de herramientas ejecutadas.
    :param input_tokens: Tokens de entrada acumulados.
    :param output_tokens: Tokens de salida acumulados.
    :param model: Nombre del modelo usado (vacío si no se indicó).
    :param route: Motivo de la elección del modelo (vacío si no se indicó).
    :param cached_calls: Llamadas respondidas por la caché del gateway.
    :param cost_usd: Costo acumulado en USD.
    """

    answer: str
    steps: int = 0
    tools_used: List[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    route: str = ""
    cached_calls: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class RunSettings:
    """Palancas de costo que aplica el agente en una pregunta.

    :param model_name: Nombre del modelo elegido (para precio y registro).
    :param route: Motivo del enrutador.
    :param history_window: Últimos mensajes de historial que se envían;
        ``None`` envía todo el historial.
    :param pricing: Tabla de precios; ``None`` no calcula costo.
    """

    model_name: str = ""
    route: str = ""
    history_window: Optional[int] = None
    pricing: Optional[Pricing] = None

    def trim(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Recorta el historial del cliente a la ventana configurada.

        :param history: Historial completo enviado por el cliente.
        :return: Los últimos ``history_window`` mensajes (ninguno si es 0).
        """
        if self.history_window is None:
            return history
        if self.history_window == 0:
            return []
        return history[-self.history_window:]


# El agente expone una sola operación pública (``run``); es su contrato.
# pylint: disable-next=too-few-public-methods
class Agent:
    """Agente único: en cada vuelta el modelo pide herramienta o responde.

    :param model: Modelo con método ``complete(messages)``.
    :param directory: Directorio de empleados.
    :param max_steps: Tope de vueltas.
    :param logger: Emisor con ``emit(event, **fields)``; ``None`` no registra.
    :param trace: Fábrica de decoradores de traza por nombre; ``None`` no traza.
    :param settings: Modelo elegido, ventana de historial y precios.
    """

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        model: Model,
        directory: EmployeeDirectory,
        max_steps: int,
        logger: Optional[Any] = None,
        trace: Optional[Callable[[str], Callable]] = None,
        settings: Optional[RunSettings] = None,
    ):
        trace = trace or (lambda name: lambda func: func)
        self._directory = directory
        self._max_steps = max_steps
        self._logger = logger
        self._settings = settings or RunSettings()
        self._complete = trace("model_call")(model.complete)
        self._call_tool = trace("tool_call")(self._run_tool)
        self._execute = trace("agent_run")(self._loop)

    def run(
        self, question: str, history: Optional[List[Dict[str, str]]] = None
    ) -> AgentResult:
        """Responde una pregunta y registra la corrida en el log.

        :param question: Pregunta de la persona usuaria.
        :param history: Historial opcional enviado por el cliente.
        :return: El resultado con respuesta, pasos, herramientas y tokens.
        """
        result, stopped = self._execute(question, history or [])
        self._emit(
            "agent_run",
            question_chars=len(question),
            history_messages=len(history or []),
            steps=result.steps,
            tools=list(result.tools_used),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            model=result.model,
            route=result.route,
            cached_calls=result.cached_calls,
            cost_usd=result.cost_usd,
            stopped=stopped,
        )
        return result

    def _emit(self, event: str, **fields: Any) -> None:
        """Escribe un evento si hay logger.

        :param event: Nombre del evento.
        :param fields: Campos del evento.
        """
        if self._logger is not None:
            self._logger.emit(event, **fields)

    def _loop(
        self, question: str, history: List[Dict[str, str]]
    ) -> Tuple[AgentResult, str]:
        """Ejecuta el bucle acotado.

        :param question: Pregunta de la persona usuaria.
        :param history: Historial enviado por el cliente.
        :return: El resultado y el motivo de parada (``answer``,
            ``invalid`` o ``step_limit``).
        """
        messages = [dict(item) for item in self._settings.trim(history)]
        messages.append({"role": "user", "content": question})
        result = AgentResult(
            answer=STEP_LIMIT_ANSWER,
            model=self._settings.model_name,
            route=self._settings.route,
        )
        for _ in range(self._max_steps):
            response = self._complete(messages)
            result.steps += 1
            result.input_tokens += response.input_tokens
            result.output_tokens += response.output_tokens
            self._account(result, response)
            action = self._parse(response.text)
            if action is None or "answer" in action:
                result.answer = self._answer_of(action)
                valid = action is not None and isinstance(action["answer"], str)
                return result, "answer" if valid else "invalid"
            raw_args = action.get("args")
            args = raw_args if isinstance(raw_args, dict) else {}
            self._emit("audit", action="tool_call", tool=action["tool"], args=args)
            outcome = self._call_tool(action)
            if isinstance(outcome, tuple):
                result.answer = outcome[0]
                return result, "invalid"
            result.tools_used.append(action["tool"])
            messages.append({"role": "assistant", "content": response.text})
            messages.append({"role": "user", "content": TOOL_RESULT_PREFIX + outcome})
        return result, "step_limit"

    def _account(self, result: AgentResult, response: Any) -> None:
        """Suma llamadas cacheadas y costo de una llamada al modelo.

        :param result: Resultado en construcción.
        :param response: Respuesta del modelo.
        """
        cached = bool(getattr(response, "cached", False))
        result.cached_calls += 1 if cached else 0
        if self._settings.pricing is not None:
            result.cost_usd += self._settings.pricing.cost(
                self._settings.model_name,
                response.input_tokens,
                response.output_tokens,
                cached,
            )

    @staticmethod
    def _answer_of(action: Optional[Dict]) -> str:
        """Obtiene el texto de respuesta de una acción.

        :param action: Acción interpretada o ``None`` si es inválida.
        :return: La respuesta o un mensaje de fallo controlado.
        """
        if action is None or not isinstance(action["answer"], str):
            return INVALID_OUTPUT_ANSWER
        return action["answer"]

    @staticmethod
    def _parse(text: str) -> Optional[Dict]:
        """Interpreta la salida del modelo sin ejecutar nada.

        :param text: Texto devuelto por el modelo.
        :return: Diccionario con ``answer`` o ``tool``; ``None`` si es inválido.
        """
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        if "answer" in data or isinstance(data.get("tool"), str):
            return data
        return None

    def _run_tool(self, action: Dict):
        """Ejecuta una herramienta permitida.

        :param action: Acción con ``tool`` y ``args``.
        :return: Texto del resultado, o una tupla ``(mensaje,)`` si falla.
        """
        args = action.get("args")
        args = args if isinstance(args, dict) else {}
        handlers = {
            "get_employee": self._tool_get_employee,
            "search_by_department": self._tool_search_department,
        }
        handler = handlers.get(action["tool"])
        if handler is None:
            return (UNKNOWN_TOOL_ANSWER,)
        return handler(args)

    def _tool_get_employee(self, args: Dict):
        """Ejecuta la herramienta ``get_employee``.

        :param args: Argumentos con ``employee_id``.
        :return: Texto del resultado, o una tupla ``(mensaje,)`` si falla.
        """
        employee_id = args.get("employee_id")
        if not isinstance(employee_id, str) or not employee_id:
            return (MISSING_ARGS_ANSWER,)
        employee = self._directory.get_employee(employee_id)
        if employee is None:
            return f"No existe el empleado {employee_id}."
        return json.dumps(employee, ensure_ascii=False)

    def _tool_search_department(self, args: Dict):
        """Ejecuta la herramienta ``search_by_department``.

        :param args: Argumentos con ``department``.
        :return: Texto del resultado, o una tupla ``(mensaje,)`` si falla.
        """
        department = args.get("department")
        if not isinstance(department, str) or not department:
            return (MISSING_ARGS_ANSWER,)
        found = self._directory.search_by_department(department)
        if not found:
            return f"No hay empleados en el departamento {department}."
        return json.dumps(found, ensure_ascii=False)
