"""Pruebas unitarias del reloj inyectable."""

from datetime import datetime, timedelta, timezone

from app.clock import FixedClock, SystemClock

START = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_fixed_clock_always_returns_the_same_instant():
    """El reloj fijo devuelve siempre el instante con el que se creo."""
    clock = FixedClock(START)
    assert clock.now() == START
    assert clock.now() == START


def test_system_clock_returns_an_aware_utc_time():
    """El reloj del sistema devuelve una hora con zona horaria UTC."""
    now = SystemClock().now()
    assert now.utcoffset() == timedelta(0)
