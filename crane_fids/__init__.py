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