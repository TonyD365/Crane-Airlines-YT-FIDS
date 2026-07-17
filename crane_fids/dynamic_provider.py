"""Thread-safe flight provider that can be updated dynamically at runtime.

This provider implements :class:`FlightProvider` and stores flights in memory.
External code (e.g. an HTTP API server) can call :meth:`set_flights` to replace
the entire flight list at any time, and the next render frame will pick up the
changes immediately.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from datetime import datetime

from .models import BoardKind, Flight

__all__ = ["DynamicFlightProvider"]

_LOG = logging.getLogger(__name__)


class DynamicFlightProvider:
    """Flight provider whose data can be replaced at runtime.

    Thread-safe: :meth:`set_flights` and :meth:`fetch` use the same lock, so
    the render loop never sees a partially-updated flight list.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flights: tuple[Flight, ...] = ()

    # ------------------------------------------------------------------ #
    # FlightProvider
    # ------------------------------------------------------------------ #
    def fetch(self, now: datetime, board: BoardKind) -> Sequence[Flight]:
        """Return the current flight list (thread-safe snapshot)."""
        with self._lock:
            if board is not BoardKind.DEPARTURES:
                return ()
            return self._flights

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_flights(self, flights: Sequence[Flight]) -> None:
        """Replace the entire flight list atomically.

        Args:
            flights: The new flight list.  It will be sorted by
                ``(scheduled, flight_number)`` before being stored.
        """
        sorted_flights = tuple(sorted(flights, key=lambda f: f.sort_key))
        with self._lock:
            self._flights = sorted_flights
        _LOG.info("DynamicFlightProvider: updated to %d flights", len(sorted_flights))

    def clear(self) -> None:
        """Remove all flights."""
        with self._lock:
            self._flights = ()
        _LOG.info("DynamicFlightProvider: cleared all flights")

    @property
    def flight_count(self) -> int:
        """Number of flights currently stored."""
        with self._lock:
            return len(self._flights)