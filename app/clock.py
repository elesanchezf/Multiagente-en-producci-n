"""Relojes inyectables: único lugar donde se consulta la hora real."""

from datetime import datetime, timedelta, timezone
from typing import Protocol


# Interfaz de un solo método: un reloj solo necesita ``now``.
# pylint: disable-next=too-few-public-methods
class Clock(Protocol):
    """Interfaz de un reloj usable por la aplicación."""

    def now(self) -> datetime:
        """Devuelve el instante actual con zona horaria UTC.

        :return: Fecha y hora conscientes de zona horaria.
        """


# Implementación de la interfaz ``Clock``, que solo exige ``now``.
# pylint: disable-next=too-few-public-methods
class SystemClock:
    """Reloj real del sistema, en UTC."""

    def now(self) -> datetime:
        """Devuelve la hora real del sistema.

        :return: Fecha y hora actuales en UTC.
        """
        return datetime.now(timezone.utc)


# Implementación de la interfaz ``Clock``, que solo exige ``now``.
# pylint: disable-next=too-few-public-methods
class FixedClock:
    """Reloj que siempre devuelve el mismo instante (para pruebas).

    :param instant: Instante que se devolverá en cada llamada.
    """

    def __init__(self, instant: datetime):
        self._instant = instant

    def now(self) -> datetime:
        """Devuelve el instante fijo.

        :return: El instante recibido al construir el reloj.
        """
        return self._instant


# Implementación de la interfaz ``Clock``, que solo exige ``now``.
# pylint: disable-next=too-few-public-methods
class SteppingClock:
    """Reloj que avanza una cantidad fija en cada lectura (para pruebas).

    :param start: Instante de la primera lectura.
    :param step_seconds: Segundos que avanza después de cada lectura.
    """

    def __init__(self, start: datetime, step_seconds: float = 1):
        self._current = start
        self._step = timedelta(seconds=step_seconds)

    def now(self) -> datetime:
        """Devuelve el instante actual y avanza el reloj.

        :return: El instante vigente antes de avanzar.
        """
        current = self._current
        self._current = current + self._step
        return current
