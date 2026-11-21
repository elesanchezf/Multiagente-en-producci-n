"""Límite de llamadas y presupuesto estimado para pruebas con proveedores reales.

Dos garantías de naturaleza distinta:

* **Límite de llamadas (exacto):** nunca se envían más de ``max_calls`` llamadas;
  la llamada que lo superaría se rechaza antes de salir. No hay reintentos: una
  llamada rechazada o fallida no se repite y las fallidas también cuentan.
* **Presupuesto en tokens y dólares (estimado, no garantizado):** antes de cada
  llamada se estima la entrada y se reserva el peor caso con ``max_output_tokens``;
  después se acumula el consumo que informa el proveedor. La estimación no es el
  conteo del tokenizador del proveedor ni incluye la plantilla de chat que este
  añada, por lo que no asegura un máximo exacto de tokens ni de dólares. El gasto
  real puede diferir y debe limitarse también en el panel del proveedor.
"""

from typing import Dict, List, Optional

from app.llm import Model, ModelResponse, ModelUnavailable
from app.pricing import Pricing

# Margen por mensaje para marcadores de rol y de fin de turno de la plantilla.
MESSAGE_OVERHEAD_TOKENS = 8


class BudgetExceeded(ModelUnavailable):
    """Una llamada se rechazó antes de enviarse por superar un tope."""


class BudgetGuard:  # pylint: disable=too-many-instance-attributes
    """Limita las llamadas (exacto) y el presupuesto (estimado).

    :param pricing: Tabla de precios.
    :param max_calls: Máximo exacto de llamadas al modelo.
    :param max_usd: Presupuesto estimado: costo acumulado más la reserva del
        peor caso de la llamada; no es un máximo garantizado de gasto.
    :param max_input_tokens: Tope de la *estimación* de entrada por llamada.
    :param max_output_tokens: Tokens de salida que se solicitan al proveedor.
    """

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(self, pricing: Pricing, max_calls: int, max_usd: float,
                 max_input_tokens: int, max_output_tokens: int):
        self._pricing = pricing
        self.max_calls = max_calls
        self.max_usd = max_usd
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.calls = 0
        self.spent_usd = 0.0
        self.tripped: Optional[str] = None
        self.usage: List[Dict] = []

    def estimate_input(self, messages: List[Dict[str, str]]) -> int:
        """Estima la entrada con los bytes UTF-8 del texto más un margen por mensaje.

        Un tokenizador BPE con respaldo por bytes no produce más tokens que bytes,
        así que es una cota alta habitual del texto; es una estimación, no una
        garantía, porque no replica el tokenizador ni la plantilla del proveedor.
        """
        size = sum(len(item.get("content", "").encode("utf-8")) for item in messages)
        return size + MESSAGE_OVERHEAD_TOKENS * len(messages)

    def reserve(self, model_name: str, messages: List[Dict[str, str]]) -> int:
        """Autoriza una llamada o lanza ``BudgetExceeded`` sin enviarla.

        :return: Tokens de entrada estimados.
        """
        estimate = self.estimate_input(messages)
        worst = self._pricing.reserve_cost(model_name, estimate,
                                           self.max_output_tokens)
        reason = None
        if self.calls + 1 > self.max_calls:
            reason = "max_calls"
        elif estimate > self.max_input_tokens:
            reason = "max_input_tokens"
        elif self.spent_usd + worst > self.max_usd:
            reason = "max_usd"
        if reason:
            self.tripped = reason
            raise BudgetExceeded(f"Budget limit reached: {reason}")
        self.calls += 1
        self.usage.append({"call": self.calls, "model": model_name,
                           "estimated_input_tokens": estimate})
        return estimate

    def record(self, model_name: str, response: ModelResponse) -> None:
        """Acumula el consumo informado por el proveedor."""
        cost = self._pricing.cost(model_name, response.input_tokens,
                                  response.output_tokens, response.cached)
        self.spent_usd += cost
        self.usage[-1].update(input_tokens=response.input_tokens,
                              output_tokens=response.output_tokens,
                              cost_usd=cost, cached=response.cached)


# Adaptador de un método que cumple la interfaz ``Model``.
# pylint: disable-next=too-few-public-methods
class BudgetedModel:
    """Envuelve un modelo para pasar cada llamada por el ``BudgetGuard``."""

    def __init__(self, model: Model, name: str, guard: BudgetGuard):
        self._model = model
        self._name = name
        self._guard = guard

    def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Reserva presupuesto, llama una sola vez y registra el consumo."""
        self._guard.reserve(self._name, messages)
        response = self._model.complete(messages)
        self._guard.record(self._name, response)
        return response


def wrap_models(models: Dict[str, Model], guard: BudgetGuard) -> Dict[str, Model]:
    """Envuelve todos los modelos con el mismo guardián."""
    return {name: BudgetedModel(model, name, guard)
            for name, model in models.items()}
