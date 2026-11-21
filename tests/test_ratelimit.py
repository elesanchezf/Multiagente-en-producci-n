"""Pruebas unitarias del limite de peticiones por cliente (sesion 4).

Supuestos de interfaz: ``app.ratelimit.RateLimiter(limit, clock)`` con
``check(client)`` que registra la peticion y devuelve un objeto con
``allowed`` (bool) y ``retry_after`` (segundos enteros, al menos 1 cuando se
niega). La ventana es deslizante de 60 segundos. El reloj es inyectado.
"""

from app.ratelimit import RateLimiter


def _filled(manual_clock, limit=2):
    """Crea un limitador cuyo cliente ``acme`` ya uso todo su cupo."""
    limiter = RateLimiter(limit, manual_clock)
    for _ in range(limit):
        assert limiter.check("acme").allowed
    return limiter


def test_the_request_over_the_limit_is_denied_with_the_seconds_left(manual_clock):
    """La peticion que excede el limite se niega e indica los segundos restantes."""
    limiter = _filled(manual_clock)
    manual_clock.advance(30)
    denied = limiter.check("acme")
    assert not denied.allowed
    assert denied.retry_after == 30


def test_retry_after_is_never_below_one_second_and_the_window_expires(manual_clock):
    """El tiempo de espera nunca baja de un segundo y la ventana termina por expirar."""
    limiter = _filled(manual_clock)
    manual_clock.advance(59.5)
    assert limiter.check("acme").retry_after == 1
    manual_clock.advance(0.5)
    assert limiter.check("acme").allowed
