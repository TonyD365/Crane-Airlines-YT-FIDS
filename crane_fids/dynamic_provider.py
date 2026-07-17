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

    def add_flight(self, flight: Flight) -> None:
        """Add a single flight to the list.

        Args:
            flight: The flight to add.  The list is re-sorted after insertion.
        """
        with self._lock:
            self._flights = tuple(sorted(self._flights + (flight,), key=lambda f: f.sort_key))
        _LOG.info("DynamicFlightProvider: added flight %s", flight.flight_number)

    def update_flight(self, flight_number: str, **updates) -> Flight | None:
        """Update a flight by flight number.

        Args:
            flight_number: The flight number to update (e.g. ``"CR101"``).
            **updates: Fields to update.  Supported: ``destination``, ``scheduled``,
                ``gate``, ``status``, ``departure``, ``remark``.

        Returns:
            The updated flight, or ``None`` if not found.
        """
        with self._lock:
            for i, flight in enumerate(self._flights):
                if flight.flight_number.upper() == flight_number.upper():
                    new_flight = Flight(
                        flight_number=flight.flight_number,
                        destination=updates.get("destination", flight.destination),
                        scheduled=updates.get("scheduled", flight.scheduled),
                        gate=updates.get("gate", flight.gate),
                        status=updates.get("status", flight.status),
                        departure=updates.get("departure", flight.departure),
                        remark=updates.get("remark", flight.remark),
                        board=flight.board,
                    )
                    self._flights = tuple(sorted(
                        self._flights[:i] + (new_flight,) + self._flights[i + 1:],
                        key=lambda f: f.sort_key,
                    ))
                    _LOG.info("DynamicFlightProvider: updated flight %s", flight_number)
                    return new_flight
        _LOG.warning("DynamicFlightProvider: flight %s not found", flight_number)
        return None

    def remove_flight(self, flight_number: str) -> Flight | None:
        """Remove a flight by flight number.

        Args:
            flight_number: The flight number to remove.

        Returns:
            The removed flight, or ``None`` if not found.
        """
        with self._lock:
            for i, flight in enumerate(self._flights):
                if flight.flight_number.upper() == flight_number.upper():
                    self._flights = self._flights[:i] + self._flights[i + 1:]
                    _LOG.info("DynamicFlightProvider: removed flight %s", flight_number)
                    return flight
        _LOG.warning("DynamicFlightProvider: flight %s not found", flight_number)
        return None

    def clear(self) -> None:
        """Remove all flights."""
        with self._lock:
            self._flights = ()
        _LOG.info("DynamicFlightProvider: cleared all flights")

    def get_flight(self, flight_number: str) -> Flight | None:
        """Get a flight by flight number.

        Args:
            flight_number: The flight number to look up.

        Returns:
            The flight, or ``None`` if not found.
        """
        with self._lock:
            for flight in self._flights:
                if flight.flight_number.upper() == flight_number.upper():
                    return flight
        return None

    @property
    def flight_count(self) -> int:
        """Number of flights currently stored."""
        with self._lock:
            return len(self._flights)
