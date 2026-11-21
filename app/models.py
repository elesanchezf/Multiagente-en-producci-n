"""Armado de los modelos barato y capaz según el proveedor."""

from typing import Dict

from app.config import Config
from app.directory import EmployeeDirectory
from app.gateway import GatewayModel
from app.llm import FakeModel, Model


def build_models(config: Config, directory: EmployeeDirectory) -> Dict[str, Model]:
    """Crea un modelo por cada nombre configurado.

    Con ``fake`` son dos modelos simulados que se llaman como ``MODEL_SMALL`` y
    ``MODEL_LARGE``; con ``gateway`` son clientes de AI Gateway.

    :param config: Configuración del servicio.
    :param directory: Directorio de empleados (modelo simulado).
    :return: Diccionario ``nombre -> modelo``.
    """
    names = {config.model_small, config.model_large}
    if config.model_provider == "gateway":
        return {name: GatewayModel(config, name) for name in names}
    return {name: FakeModel(directory, name) for name in names}
