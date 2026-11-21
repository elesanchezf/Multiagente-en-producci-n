"""Claves por cliente: análisis de ``API_KEYS`` e identificación del cliente.

Seguridad: una clave nunca se escribe en el log, en la traza, en un mensaje de
error ni en el código. Los errores solo indican la posición y el largo de la
entrada que falla.

Limitación conocida y aceptada por la persona que aprobó el plan: los
intentos con clave inválida NO tienen límite por origen. Solo el cliente ya
autenticado tiene límite de peticiones (``ratelimit.py``). La mitigación es
exigir claves de al menos 16 caracteres en producción (``compliance.py``) y
comparar en tiempo constante.
"""

import hmac
from typing import Dict, Optional

from app.errors import ConfigError

MIN_KEY_LENGTH = 16
HEADER_NAME = "X-API-Key"
INVALID_KEY_DETAIL = "invalid or missing API key"


def _malformed(position: int, entry: str, reason: str) -> ConfigError:
    """Crea el error de una entrada inválida sin revelar su contenido.

    :param position: Posición de la entrada, desde 1.
    :param entry: Entrada original; solo se usa su largo.
    :param reason: Motivo fijo, sin datos de la entrada.
    :return: El error de configuración.
    """
    return ConfigError(
        f"API_KEYS entry {position} is invalid: {reason} (length {len(entry)})"
    )


def parse_api_keys(raw: str) -> Dict[str, str]:
    """Analiza ``API_KEYS`` con la forma ``cliente:clave,cliente2:clave2``.

    Se ignoran los espacios alrededor de cliente y clave. La clave puede
    contener dos puntos; el cliente es lo anterior al primero.

    :param raw: Valor de la variable; vacío significa sin clientes.
    :return: Diccionario de cliente a clave.
    :raises ConfigError: Si una entrada está vacía, sin dos puntos, sin
        cliente o sin clave, o si un cliente se repite. El mensaje no incluye
        valores.
    """
    if not raw.strip():
        return {}
    keys: Dict[str, str] = {}
    for position, entry in enumerate(raw.split(","), start=1):
        text = entry.strip()
        client, separator, key = text.partition(":")
        client, key = client.strip(), key.strip()
        if not text:
            raise _malformed(position, entry, "empty entry")
        if not separator:
            raise _malformed(position, entry, "expected client:key")
        if not client or not key:
            raise _malformed(position, entry, "client or key is empty")
        if client in keys:
            raise _malformed(position, entry, "client is repeated")
        keys[client] = key
    return keys


def identify_client(keys: Dict[str, str], presented: Optional[str]) -> Optional[str]:
    """Busca al cliente dueño de la clave presentada.

    Compara con ``hmac.compare_digest`` y recorre todas las claves para no
    revelar por tiempo cuál coincidió.

    :param keys: Diccionario de cliente a clave.
    :param presented: Valor del encabezado ``X-API-Key`` o ``None``.
    :return: El nombre del cliente, o ``None`` si falta o no coincide.
    """
    if not presented:
        return None
    candidate = presented.encode("utf-8")
    found: Optional[str] = None
    for client, key in keys.items():
        if hmac.compare_digest(candidate, key.encode("utf-8")):
            found = client
    return found
