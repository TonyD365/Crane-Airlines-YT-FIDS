"""Domain model of the departure board.

This module is deliberately free of any I/O, Pillow or FFmpeg dependency: it
describes *what* a flight is, never *where it comes from* or *how it is drawn*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum

__all__ = ["BoardKind", "Flight", "FlightStatus"]


class BoardKind(StrEnum):
    """Which board a flight belongs to.

    Only :attr:`DEPARTURES` is rendered today; the enum exists so that an
    arrivals page can be added later without touching the data model.
    """

    DEPARTURES = "DEPARTURES"
    ARRIVALS = "ARRIVALS"


class FlightStatus(Enum):
    """Operational status of a flight, with its presentation semantics.

    The colour and blink policy live next to the status because they are part
    of the airport display *convention*, not of a particular renderer.  The
    renderer merely asks the status how it wants to be shown.
    """

    ON_TIME = ("ON TIME", (0, 208, 96), False)
    GATE_OPEN = ("GATE OPEN", (120, 220, 255), False)
    EC_BOARDING = ("ECONOMY CLASS BOARDING", (255, 214, 0), True)
    BC_BOARDING = ("BUSINESS CLASS BOARDING", (255, 214, 0), True)
    FC_BOARDING = ("FIRST CLASS BOARDING", (255, 214, 0), True)
    DN_BOARDING = ("DONORS BOARDING", (255, 214, 0), True)
    FINAL_CALL = ("FINAL CALL", (255, 56, 56), True)
    DELAYED = ("DELAYED", (255, 138, 0), False)
    CANCELLED = ("CANCELLED", (255, 56, 56), False)
    DEPARTED = ("DEPARTED", (150, 158, 170), False)

    def __init__(self, label: str, colour: tuple[int, int, int], blinking: bool) -> None:
        self._label = label
        self._colour = colour
        self._blinking = blinking

    @property
    def label(self) -> str:
        """Text shown in the STATUS column."""
        return self._label

    @property
    def colour(self) -> tuple[int, int, int]:
        """RGB colour used for the STATUS column."""
        return self._colour

    @property
    def blinking(self) -> bool:
        """Whether the status must blink to attract attention."""
        return self._blinking

    @classmethod
    def from_label(cls, label: str) -> FlightStatus:
        """Parse a human label such as ``"FINAL CALL"``.

        Raises:
            ValueError: when the label is unknown.
        """
        normalised = label.strip().upper()
        for status in cls:
            if status.label == normalised or status.name == normalised.replace(" ", "_"):
                return status
        raise ValueError(f"Unknown flight status: {label!r}")


@dataclass(frozen=True, slots=True)
class Flight:
    """A single row of the board.

    Attributes:
        flight_number: IATA-like designator, e.g. ``"CR101"``.
        destination: Destination city name shown in the DESTINATION column.
        departure: Departure city name shown in the DEPARTURE column.
        scheduled: Scheduled time of departure (timezone aware or naive local).
        gate: Gate identifier, e.g. ``"A12"``.
        status: Current :class:`FlightStatus`.
        remark: Optional secondary text (e.g. ``"NEW TIME 14:35"``).
        board: Which board this flight belongs to.
    """

    flight_number: str
    destination: str
    scheduled: datetime
    gate: str
    status: FlightStatus
    departure: str = ""
    remark: str = ""
    board: BoardKind = BoardKind.DEPARTURES

    def __post_init__(self) -> None:
        if not self.flight_number.strip():
            raise ValueError("flight_number must not be empty")
        if not self.destination.strip():
            raise ValueError("destination must not be empty")

    @property
    def scheduled_label(self) -> str:
        """Scheduled time formatted for the TIME column (24h, UTC)."""
        # Ensure UTC timezone
        scheduled = self.scheduled
        if scheduled.tzinfo is None:
            from datetime import timezone
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        return scheduled.strftime("%H:%M")

    @property
    def sort_key(self) -> tuple[datetime, str]:
        """Deterministic ordering: by time, then flight number."""
        return self.scheduled, self.flight_number

    def with_status(self, status: FlightStatus, remark: str = "") -> Flight:
        """Return a copy of this flight carrying a new status.

        The model is immutable, so state transitions always create new values;
        this keeps the render loop free of surprise mutations.
        """
        return Flight(
            flight_number=self.flight_number,
            destination=self.destination,
            scheduled=self.scheduled,
            gate=self.gate,
            status=status,
            departure=self.departure,
            remark=remark or self.remark,
            board=self.board,
        )
