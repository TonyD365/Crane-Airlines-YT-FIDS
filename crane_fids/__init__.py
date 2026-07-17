"""Crane Airlines YouTube FIDS.

A production-grade airport Flight Information Display System that renders an
airport-style departure board with Pillow and streams it to an RTMP endpoint
(YouTube Live) through FFmpeg.

The package is intentionally split into independent, highly cohesive modules:

* :mod:`crane_fids.config`         -- environment driven configuration
* :mod:`crane_fids.models`         -- domain entities (Flight, FlightStatus)
* :mod:`crane_fids.flight_manager` -- flight data sourcing / caching
* :mod:`crane_fids.renderer`       -- Pillow based frame composition
* :mod:`crane_fids.stream_engine`  -- FFmpeg process supervision
* :mod:`crane_fids.application`    -- orchestration / main loop
* :mod:`crane_fids.dynamic_provider` -- runtime-updatable flight provider

Quick Start
-----------

**1. Start the broadcast (default uses DynamicFlightProvider with 12 example flights):**

    python app.py

**2. Preview a single frame:**

    python app.py --preview

**3. Control flights from external Python code:**

    from crane_fids import Flight, FlightStatus
    from datetime import datetime, timezone

    # Add a flight
    crane_fids.add_flight(
        Flight("CR999", "DUBAI", datetime.now(timezone.utc), "F01", FlightStatus.ON_TIME)
    )

    # Update a flight
    crane_fids.update_flight("CR999", status=FlightStatus.BOARDING, gate="F02")

    # Remove a flight
    crane_fids.remove_flight("CR999")

    # Replace all flights
    crane_fids.set_flights([...])

    # Clear all flights
    crane_fids.clear()

    # Query a flight
    flight = crane_fids.get_flight("CR101")

    # Get flight count
    count = crane_fids.get_flight_count()

**4. Use your own provider:**

    from crane_fids import DynamicFlightProvider, Flight, FlightStatus
    from crane_fids.config import Config
    from crane_fids.application import build_application
    from datetime import datetime, timezone

    provider = DynamicFlightProvider()
    provider.set_flights([...])

    config = Config.from_env()
    app = build_application(config, provider=provider)
    app.run()

Timezones
---------

All times in the FIDS are displayed in **UTC**.  When creating ``Flight``
objects, pass timezone-aware ``datetime`` objects in UTC, or naive datetimes
(which will be interpreted as UTC).

Public API
----------

Convenience Functions
    ``add_flight()``, ``update_flight()``, ``remove_flight()``, ``get_flight()``,
    ``set_flights()``, ``clear()``, ``get_flight_count()`` -- control the global
    flight provider from external code.

DynamicFlightProvider
    Thread-safe flight provider with full CRUD operations.

Flight
    Immutable flight data class.

FlightStatus
    Enumeration of flight statuses with colours and blink behaviour.

BoardKind
    DEPARTURES or ARRIVALS.
"""

from __future__ import annotations

from .dynamic_provider import DynamicFlightProvider
from .models import BoardKind, Flight, FlightStatus

__all__ = [
    "__version__",
    "DynamicFlightProvider",
    "Flight",
    "FlightStatus",
    "BoardKind",
    "add_flight",
    "update_flight",
    "remove_flight",
    "get_flight",
    "set_flights",
    "clear",
    "get_flight_count",
]

__version__ = "1.0.0"

# ------------------------------------------------------------------ #
# Global flight provider (shared with app.py)
# ------------------------------------------------------------------ #
_provider = DynamicFlightProvider()


def add_flight(flight: Flight) -> None:
    """Add a flight to the global provider."""
    _provider.add_flight(flight)


def update_flight(flight_number: str, **updates) -> Flight | None:
    """Update a flight in the global provider."""
    return _provider.update_flight(flight_number, **updates)


def remove_flight(flight_number: str) -> Flight | None:
    """Remove a flight from the global provider."""
    return _provider.remove_flight(flight_number)


def get_flight(flight_number: str) -> Flight | None:
    """Get a flight from the global provider."""
    return _provider.get_flight(flight_number)


def set_flights(flights: list[Flight]) -> None:
    """Replace all flights in the global provider."""
    _provider.set_flights(flights)


def clear() -> None:
    """Clear all flights from the global provider."""
    _provider.clear()


def get_flight_count() -> int:
    """Get the number of flights in the global provider."""
    return _provider.flight_count
