"""Pruebas unitarias del log JSON y de la validacion del id de peticion.

Supuestos de interfaz: ``JsonLogger(service, clock, stream=None)`` con
``emit(event, **fields)``; ``request_id_var`` (``ContextVar``) y
``resolve_request_id(raw)`` que devuelve ``raw`` si es valido o un UUID nuevo.
"""

import io
import json
import uuid
from datetime import datetime, timezone

from app.clock import FixedClock
from app.observability import JsonLogger, request_id_var, resolve_request_id

START = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_each_event_is_one_json_line_with_the_required_fields():
    """Cada evento se escribe como una linea JSON con los campos obligatorios."""
    stream = io.StringIO()
    logger = JsonLogger("hr-assistant", FixedClock(START), stream)
    token = request_id_var.set("req-1")
    try:
        logger.emit("request", method="GET", path="/health", status=200)
        logger.emit("audit", action="tool_call", tool="get_employee", args={})
    finally:
        request_id_var.reset(token)
    lines = stream.getvalue().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "request"
    assert first["service"] == "hr-assistant"
    assert first["request_id"] == "req-1"
    assert first["status"] == 200
    assert datetime.fromisoformat(first["ts"].replace("Z", "+00:00")) == START


def test_a_valid_client_id_is_kept_and_a_missing_one_is_generated():
    """Un id de peticion valido se conserva y uno ausente se genera como UUID."""
    assert resolve_request_id("demo-123") == "demo-123"
    assert uuid.UUID(resolve_request_id(None))


def test_hostile_or_oversized_ids_are_replaced_by_a_uuid():
    """Un id hostil, vacio o demasiado largo se reemplaza por un UUID."""
    hostile = ["abc\n{\"event\": \"forged\"}", "x" * 300, "", "a b\tc"]
    for raw in hostile:
        replaced = resolve_request_id(raw)
        assert replaced != raw
        assert uuid.UUID(replaced)
