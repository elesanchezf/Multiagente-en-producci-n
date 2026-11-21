"""Adaptador opcional de trazas de LangSmith.

Sin la biblioteca, sin la clave o con las trazas apagadas, el decorador no
altera la función y no se intenta ninguna conexión. La clave nunca se lee
aquí ni se escribe en el log.
"""

import functools
from typing import Any, Callable, Mapping, Optional

HIDDEN_VALUE = "[hidden]"
TRUE_VALUES = ("true", "1", "yes")


def is_tracing_enabled(env: Mapping[str, str]) -> bool:
    """Indica si las trazas deben activarse.

    :param env: Variables de entorno.
    :return: Verdadero solo con ``LANGSMITH_TRACING=true`` y clave no vacía.
    """
    flag = (env.get("LANGSMITH_TRACING") or "").strip().lower()
    key = (env.get("LANGSMITH_API_KEY") or "").strip()
    return flag in TRUE_VALUES and bool(key)


def redact(value: Any, hide: bool) -> Any:
    """Reemplaza un valor cuando debe ocultarse.

    :param value: Valor original.
    :param hide: Si es verdadero se devuelve un marcador en su lugar.
    :return: El valor original o el marcador.
    """
    return HIDDEN_VALUE if hide else value


def _mask(data: Any, hide: bool) -> Any:
    """Prepara entradas o salidas para LangSmith, que espera un diccionario.

    :param data: Datos originales.
    :param hide: Si es verdadero se envía solo un marcador.
    :return: Los datos o un diccionario con el marcador.
    """
    return {"data": redact(data, True)} if hide else data


def _load_traceable():
    """Importa ``traceable`` y ``get_current_run_tree`` si existen.

    :return: Tupla ``(traceable, get_current_run_tree)`` o ``(None, None)``.
    """
    try:
        # pylint: disable=import-outside-toplevel
        from langsmith import traceable
        from langsmith.run_helpers import get_current_run_tree
        # pylint: enable=import-outside-toplevel
    except ImportError:
        return None, None
    return traceable, get_current_run_tree


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def traced(
    name: str,
    enabled: bool,
    hide_inputs: bool = True,
    hide_outputs: bool = True,
    request_id_getter: Callable[[], str] = lambda: "",
    client_getter: Callable[[], Optional[str]] = lambda: None,
) -> Callable:
    """Crea un decorador que registra la función como traza de LangSmith.

    :param name: Nombre de la traza.
    :param enabled: Si es falso el decorador devuelve la función intacta.
    :param hide_inputs: No enviar las entradas.
    :param hide_outputs: No enviar las salidas.
    :param request_id_getter: Obtiene el ``request_id`` para los metadatos.
    :param client_getter: Obtiene el nombre del cliente (nunca su clave) para
        los metadatos; si devuelve ``None`` no se agrega.
    :return: El decorador.
    """
    traceable, get_run_tree = _load_traceable() if enabled else (None, None)

    def decorator(func: Callable) -> Callable:
        if traceable is None:
            return func

        @functools.wraps(func)
        def with_metadata(*args: Any, **kwargs: Any) -> Any:
            run_tree = get_run_tree()
            if run_tree is not None:
                run_tree.metadata["request_id"] = request_id_getter()
                client = client_getter()
                if client is not None:
                    run_tree.metadata["client"] = client
            return func(*args, **kwargs)

        return traceable(
            name=name,
            process_inputs=lambda data: _mask(data, hide_inputs),
            process_outputs=lambda data: _mask(data, hide_outputs),
        )(with_metadata)

    return decorator
