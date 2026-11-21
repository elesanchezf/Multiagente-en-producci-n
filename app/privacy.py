"""Detección conservadora de información sensible; no sustituye una solución DLP."""

import json
import re
import unicodedata

PUBLIC_FIELDS = ("id", "name", "department", "role", "start_date", "status")
PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I),
    "phone": re.compile(r"(?<!\w)(?:\+?\d[\s().-]*){10,15}(?!\w)"),
    "curp": re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.I),
    "rfc": re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.I),
    "credential": re.compile(
        r"(?:\bBearer\s+\S+|\b(?:sk-|cfut_)[\w-]{8,}|"
        r"\b(?:api[_ -]?key|password|contraseña|token)\s*[:=]\s*\S+)", re.I
    ),
}


class SensitiveDataError(Exception):
    """Señal sin valores originales para detener una salida o evidencia sensible."""

    def __init__(self, stage, kinds):
        super().__init__("Sensitive information blocked")
        self.stage = stage
        self.kinds = sorted(kinds)


def sensitive_kinds(value):
    """Devuelve categorías, nunca los valores; inspecciona estructuras JSON."""
    if isinstance(value, dict):
        return set().union(*(sensitive_kinds(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(sensitive_kinds(item) for item in value))
    text = unicodedata.normalize("NFKC", str(value))
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return {name for name, pattern in PATTERNS.items() if pattern.search(text)}


def check_model_text(text):
    """Detecta también valores con escapes JSON antes de usar la salida del LLM."""
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        value = text
    kinds = sensitive_kinds(value)
    if kinds:
        raise SensitiveDataError("model_output", kinds)


def public_record(record):
    """Proyecta campos autorizados antes de enviarlos a un modelo externo."""
    safe = {key: record[key] for key in PUBLIC_FIELDS if key in record}
    kinds = sensitive_kinds(safe)
    if kinds:
        raise SensitiveDataError("directory", kinds)
    return safe
