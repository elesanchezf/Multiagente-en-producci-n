"""Precios por modelo y costo de cada llamada."""

import json
from pathlib import Path
from typing import Dict, Union

TOKENS_PER_UNIT = 1_000_000


class PricingError(Exception):
    """Error al cargar la tabla de precios o al buscar un modelo."""


class Pricing:
    """Tabla de precios en USD por millón de tokens.

    :param prices: Diccionario ``modelo -> {"input": x, "output": y}``.
    """

    def __init__(self, prices: Dict[str, Dict[str, float]]):
        self._prices = prices

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Pricing":
        """Carga la tabla desde un archivo JSON.

        :param path: Ruta del archivo.
        :return: La tabla de precios.
        :raises PricingError: Si el archivo falta o tiene formato inválido.
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as error:
            raise PricingError(f"Cannot read prices file: {path}") from error
        except json.JSONDecodeError as error:
            raise PricingError(f"Malformed prices file: {path}") from error
        models = data.get("models") if isinstance(data, dict) else None
        valid = isinstance(models, dict) and all(
            isinstance(price, dict)
            and isinstance(price.get("input"), (int, float))
            and isinstance(price.get("output"), (int, float))
            for price in models.values()
        )
        if not valid:
            raise PricingError(f"Prices file needs a valid 'models' table: {path}")
        return cls(models)

    def has_model(self, model: str) -> bool:
        """Indica si el modelo tiene precio.

        :param model: Nombre del modelo.
        :return: Verdadero si está en la tabla.
        """
        return model in self._prices

    def cost(
        self, model: str, input_tokens: int, output_tokens: int, cached: bool = False
    ) -> float:
        """Calcula el costo de una llamada.

        :param model: Nombre del modelo usado.
        :param input_tokens: Tokens de entrada.
        :param output_tokens: Tokens de salida.
        :param cached: Si la caché respondió, la llamada no cuesta.
        :return: Costo en USD.
        :raises PricingError: Si el modelo no tiene precio.
        """
        price = self._prices.get(model)
        if price is None:
            raise PricingError(f"No price for model {model!r}")
        if cached:
            return 0.0
        total = input_tokens * price["input"] + output_tokens * price["output"]
        return total / TOKENS_PER_UNIT
