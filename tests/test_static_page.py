"""Pruebas de seguridad de la pagina web estatica."""

import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"


def test_page_keeps_the_key_in_session_storage_in_a_password_field():
    """La pagina guarda la clave en sessionStorage y la captura en un campo password."""
    html = PAGE.read_text(encoding="utf-8")
    field = re.search(r"<input[^>]*data-testid=\"api-key\"[^>]*>", html)
    assert field is not None
    assert 'type="password"' in field.group(0)
    assert "sessionStorage" in html
    assert "localStorage" not in html
    assert "X-API-Key" in html
    assert "Clave inválida" in html
    assert "Demasiadas preguntas; espera" in html
    assert not re.search(r"fake-key|API_KEYS", html)


def test_page_renders_text_without_inner_html():
    """La pagina pinta texto con textContent y no usa innerHTML."""
    html = PAGE.read_text(encoding="utf-8")
    assert "textContent" in html
    assert "innerHTML" not in html
