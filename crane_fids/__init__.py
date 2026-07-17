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

    import app
    from crane_fids import Flight, FlightStatus
    from datetime import datetime, timezone

    # Add a flight
    app.provider.add_flight(
        Flight("CR999", "DUBAI", datetime.now(timezone.utc), "F01", FlightStatus.ON_TIME)
    )

    # Update a flight
    app.provider.update_flight("CR999", status=FlightStatus.BOARDING, gate="F02")

    # Remove a flight
    app.provider.remove_flight("CR999")

    # Replace all flights
    app.provider.set_flights([...])

    # Clear all flights
    app.provider.clear()

    # Query a flight
    flight = app.provider.get_flight("CR101")

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
]

__version__ = "1.0.0"
