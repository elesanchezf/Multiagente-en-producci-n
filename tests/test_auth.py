"""Pruebas unitarias de las claves por cliente (sesion 4).

Supuestos de interfaz: ``app.auth.parse_api_keys(raw)`` devuelve un ``dict``
cliente a clave y lanza ``ConfigError`` si la lista esta mal formada;
``app.auth.identify_client(keys, presented)`` devuelve el nombre del cliente
o ``None``. Todas las claves son ficticias.
"""

import pytest

from app.auth import identify_client, parse_api_keys
from app.config import ConfigError

KEY_A = "fake-key-acme-0000000000"
KEY_B = "fake-key-globex-000000000"

MALFORMED = [
    ("no colon", "acme-without-colon-value", "acme-without-colon-value"),
    ("empty client", ":fake-key-orphan-0000000", "fake-key-orphan-0000000"),
    ("empty key", "acme:", "acme"),
    ("empty entry", f"acme:{KEY_A},,globex:{KEY_B}", KEY_B),
    ("duplicate client", f"acme:{KEY_A},acme:{KEY_B}", KEY_B),
]


def test_valid_entries_become_clients_even_with_spaces_and_colons():
    """Las entradas validas forman el diccionario aun con espacios y dos puntos."""
    assert len(parse_api_keys("")) == 0
    assert parse_api_keys(f" acme : {KEY_A} , globex:{KEY_B} ") == {
        "acme": KEY_A,
        "globex": KEY_B,
    }
    assert parse_api_keys("acme:part1:part2-0000000000") == {
        "acme": "part1:part2-0000000000"
    }


def test_malformed_entries_fail_without_revealing_their_value():
    """Una lista mal formada lanza ConfigError sin filtrar claves en el mensaje."""
    for label, raw, secret in MALFORMED:
        with pytest.raises(ConfigError) as error:
            parse_api_keys(raw)
        assert secret not in str(error.value), label
        assert KEY_A not in str(error.value), label


def test_a_client_is_identified_only_by_its_exact_key():
    """Solo la clave exacta identifica al cliente; cualquier otra devuelve None."""
    keys = {"acme": KEY_A, "globex": KEY_B}
    assert identify_client(keys, KEY_B) == "globex"
    assert identify_client(keys, KEY_A + "x") is None
    assert identify_client(keys, KEY_A[:-1]) is None
    assert identify_client(keys, "") is None
    assert identify_client(keys, None) is None
