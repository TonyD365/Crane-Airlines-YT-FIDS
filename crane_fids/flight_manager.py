"""Flight data sourcing.

The renderer must never know where flights come from.  Everything in this
module therefore hides behind :class:`FlightProvider`, a narrow protocol with a
single method.  Today the only implementation is :class:`StaticFlightProvider`
(hard-coded timetable, no network at all); tomorrow a ``JsonFlightProvider``,
``RestFlightProvider`` or ``DatabaseFlightProvider`` can be dropped in without
a single change anywhere else in the code base.
"""

from __future__ import annotations

import logging
import random
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from .models import BoardKind, Flight, FlightStatus

__all__ = [
    "FlightManager",
    "FlightProvider",
    "ScheduleEntry",
    "StaticFlightProvider",
]

_LOG = logging.getLogger(__name__)


@runtime_checkable
class FlightProvider(Protocol):
    """Source of truth for flight data."""

    def fetch(self, now: datetime, board: BoardKind) -> Sequence[Flight]:
        """Return every known flight for ``board`` at instant ``now``.

        Implementations may block (network, disk); they are only ever called
        from :class:`FlightManager`, never from the render loop.
        """
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    """One line of a static timetable."""

    flight_number: str
    destination: str
    gate: str
    #: Minutes after the top of the rolling schedule window.
    offset_minutes: int


# Base timetable.  Times are relative, so the board always looks "live"
# regardless of when the container is started.
_DEFAULT_SCHEDULE: tuple[ScheduleEntry, ...] = (
    ScheduleEntry("CR104", "NEW YORK", "A12", 0),
    ScheduleEntry("CR102", "CHICAGO", "B08", 12),
    ScheduleEntry("CR103", "TORONTO", "C11", 24),
    ScheduleEntry("CR201", "VANCOUVER", "D09", 36),
    ScheduleEntry("CR301", "LONDON", "E73", 48),
    ScheduleEntry("CR401", "PARIS", "A12", 60),
    ScheduleEntry("CR118", "FRANKFURT", "B08", 72),
    ScheduleEntry("CR233", "TOKYO", "C11", 84),
    ScheduleEntry("CR507", "SHANGHAI", "D09", 96),
    ScheduleEntry("CR612", "BEIJING", "E73", 108),
    ScheduleEntry("CR715", "SINGAPORE", "A12", 120),
    ScheduleEntry("CR808", "SYDNEY", "B08", 132),
    ScheduleEntry("CR129", "NEW YORK", "C11", 144),
    ScheduleEntry("CR342", "LONDON", "D09", 156),
    ScheduleEntry("CR455", "TORONTO", "E73", 168),
    ScheduleEntry("CR566", "PARIS", "A12", 180),
)

#: Deterministic disruption table: flight number -> (delay minutes).
_DISRUPTIONS: dict[str, int] = {
    "CR301": 45,
    "CR507": 20,
    "CR129": 35,
}


#: Status ladder, read top-down: the first threshold (in minutes before the
#: expected departure) that the flight is inside wins.  Encoding the airport
#: convention as data keeps :meth:`StaticFlightProvider._derive_status` free of
#: magic numbers and makes the policy reviewable at a glance.
_STATUS_LADDER: tuple[tuple[float, FlightStatus], ...] = (
    (-5.0, FlightStatus.DEPARTED),
    (5.0, FlightStatus.FINAL_CALL),
    (12.0, FlightStatus.LAST_CALL),
    (30.0, FlightStatus.BOARDING),
    (45.0, FlightStatus.GATE_OPEN),
)

#: A delay is announced as DELAYED until boarding of the new time approaches.
_DELAY_ANNOUNCE_WINDOW: timedelta = timedelta(minutes=20)

#: How far in the past a departure stays on the board before it rolls forward.
_ROLL_OVER_GRACE: timedelta = timedelta(minutes=12)


class StaticFlightProvider:
    """Hard-coded, network-free timetable.

    The schedule rolls forward continuously: departures in the past are pushed
    one full cycle into the future, so the board never runs dry during a 24x7
    stream.  Status is derived from the remaining time to departure, which
    produces a realistic, self-animating board without any external feed.
    """

    def __init__(
        self,
        schedule: Sequence[ScheduleEntry] = _DEFAULT_SCHEDULE,
        *,
        disruptions: dict[str, int] | None = None,
        cycle_minutes: int = 192,
    ) -> None:
        if not schedule:
            raise ValueError("schedule must not be empty")
        self._schedule = tuple(schedule)
        self._disruptions = dict(_DISRUPTIONS if disruptions is None else disruptions)
        self._cycle = timedelta(minutes=cycle_minutes)

    # ------------------------------------------------------------------ #
    # FlightProvider
    # ------------------------------------------------------------------ #
    def fetch(self, now: datetime, board: BoardKind) -> Sequence[Flight]:
        """Materialise the rolling timetable for ``now``."""
        if board is not BoardKind.DEPARTURES:
            return ()

        anchor = now.replace(second=0, microsecond=0) - timedelta(minutes=10)
        flights: list[Flight] = []
        for entry in self._schedule:
            scheduled = anchor + timedelta(minutes=entry.offset_minutes)
            while scheduled < now - _ROLL_OVER_GRACE:
                scheduled += self._cycle
            delay = self._disruptions.get(entry.flight_number, 0)
            status, remark = self._derive_status(now, scheduled, delay)
            flights.append(
                Flight(
                    flight_number=entry.flight_number,
                    destination=entry.destination,
                    scheduled=scheduled,
                    gate=entry.gate,
                    status=status,
                    remark=remark,
                    board=board,
                )
            )
        flights.sort(key=lambda flight: flight.sort_key)
        return tuple(flights)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _derive_status(
        now: datetime, scheduled: datetime, delay_minutes: int
    ) -> tuple[FlightStatus, str]:
        """Map "minutes until departure" onto an airport status convention."""
        if delay_minutes:
            expected = scheduled + timedelta(minutes=delay_minutes)
            if now < expected - _DELAY_ANNOUNCE_WINDOW:
                return FlightStatus.DELAYED, f"NEW TIME {expected.strftime('%H:%M')}"
            minutes_left = (expected - now).total_seconds() / 60.0
        else:
            minutes_left = (scheduled - now).total_seconds() / 60.0

        for threshold, status in _STATUS_LADDER:
            if minutes_left <= threshold:
                return status, ""
        return FlightStatus.ON_TIME, ""


class RandomisedStaticFlightProvider(StaticFlightProvider):
    """Static provider whose disruptions are reshuffled every hour.

    Useful for a long-running stream: the board keeps telling a slightly
    different story each hour while remaining fully offline and deterministic
    within the hour (so a restart does not visibly jump).
    """

    def fetch(self, now: datetime, board: BoardKind) -> Sequence[Flight]:
        self._disruptions = self._roll_disruptions(now)
        return super().fetch(now, board)

    def _roll_disruptions(self, now: datetime) -> dict[str, int]:
        rng = random.Random(now.strftime("%Y%m%d%H"))
        candidates = [entry.flight_number for entry in self._schedule]
        chosen = rng.sample(candidates, k=min(3, len(candidates)))
        return {number: rng.choice((15, 20, 35, 45, 60)) for number in chosen}


class FlightManager:
    """Caching facade in front of a :class:`FlightProvider`.

    The render loop calls :meth:`current_flights` up to ``FPS`` times per
    second; the provider is consulted at most once per refresh interval.  All
    provider failures are absorbed here: the last good snapshot keeps being
    served, so a broken data source can never take the stream down.
    """

    def __init__(
        self,
        provider: FlightProvider,
        *,
        refresh_seconds: int = 30,
        board: BoardKind = BoardKind.DEPARTURES,
    ) -> None:
        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be positive")
        self._provider = provider
        self._refresh = timedelta(seconds=refresh_seconds)
        self._board = board
        self._lock = threading.Lock()
        self._cache: tuple[Flight, ...] = ()
        self._fetched_at: datetime | None = None
        self._consecutive_failures = 0

    @property
    def board(self) -> BoardKind:
        """The board this manager serves."""
        return self._board

    def current_flights(self, now: datetime) -> tuple[Flight, ...]:
        """Return the cached flight list, refreshing it when stale."""
        with self._lock:
            if self._is_stale(now):
                self._refresh_locked(now)
            return self._cache

    def invalidate(self) -> None:
        """Force the next :meth:`current_flights` call to hit the provider."""
        with self._lock:
            self._fetched_at = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _is_stale(self, now: datetime) -> bool:
        return self._fetched_at is None or (now - self._fetched_at) >= self._refresh

    def _refresh_locked(self, now: datetime) -> None:
        try:
            flights = tuple(self._provider.fetch(now, self._board))
        except Exception:
            self._consecutive_failures += 1
            _LOG.exception(
                "Flight provider %s failed (%d consecutive failures); serving cached data",
                type(self._provider).__name__,
                self._consecutive_failures,
            )
            # Do not update ``_fetched_at``: retry on the next frame, but do not
            # hammer a broken source more than once per refresh window either.
            self._fetched_at = now
            return

        if self._consecutive_failures:
            _LOG.info("Flight provider recovered after %d failures", self._consecutive_failures)
        self._consecutive_failures = 0
        self._cache = flights
        self._fetched_at = now
        _LOG.debug("Refreshed %d flights for board %s", len(flights), self._board.value)
