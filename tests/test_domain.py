"""Tests for configuration, domain models and flight sourcing."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from crane_fids.config import Config, ConfigError, redact_rtmp_url
from crane_fids.flight_manager import (
    FlightManager,
    FlightProvider,
    ScheduleEntry,
    StaticFlightProvider,
)
from crane_fids.models import BoardKind, Flight, FlightStatus


class TestConfig:
    def test_defaults(self) -> None:
        config = Config.from_env({})
        assert config.video.size == (1920, 1080)
        assert config.video.fps == 30
        assert config.stream.enabled is False  # dry-run without RTMP_URL

    def test_overrides(self) -> None:
        config = Config.from_env(
            {"WIDTH": "1280", "HEIGHT": "720", "FPS": "25", "LOG_LEVEL": "debug"}
        )
        assert config.video.size == (1280, 720)
        assert config.video.frame_bytes == 1280 * 720 * 3
        assert config.log_level == "DEBUG"

    @pytest.mark.parametrize(
        "env",
        [
            {"FPS": "0"},
            {"FPS": "not-a-number"},
            {"WIDTH": "100000"},
            {"LOG_LEVEL": "LOUD"},
            {"AUDIO_ENABLED": "maybe"},
        ],
    )
    def test_invalid_env_is_rejected(self, env: dict[str, str]) -> None:
        with pytest.raises(ConfigError):
            Config.from_env(env)

    def test_odd_frame_size_is_rejected(self) -> None:
        with pytest.raises(ConfigError):
            Config.from_env({"WIDTH": "1281"})

    def test_stream_key_is_never_logged(self) -> None:
        config = Config.from_env({"RTMP_URL": "rtmp://a.rtmp.youtube.com/live2/super-secret"})
        assert "super-secret" not in config.describe()
        assert "super-secret" not in redact_rtmp_url(config.stream.rtmp_url)


class TestModels:
    def test_status_presentation(self) -> None:
        assert FlightStatus.EC_BOARDING.blinking is True
        assert FlightStatus.ON_TIME.blinking is False
        assert FlightStatus.from_label("final call") is FlightStatus.FINAL_CALL

    def test_unknown_status(self) -> None:
        with pytest.raises(ValueError):
            FlightStatus.from_label("TELEPORTED")

    def test_flight_is_immutable_and_validated(self) -> None:
        flight = Flight(
            "CR101", "NEW YORK", datetime(2026, 1, 1, 9, 5), "A12", FlightStatus.ON_TIME
        )
        assert flight.scheduled_label == "09:05"
        with pytest.raises(AttributeError):
            flight.gate = "B01"  # type: ignore[misc]
        with pytest.raises(ValueError):
            Flight("", "NEW YORK", datetime.now(), "A12", FlightStatus.ON_TIME)

    def test_with_status_returns_a_copy(self) -> None:
        flight = Flight("CR101", "NEW YORK", datetime.now(), "A12", FlightStatus.ON_TIME)
        updated = flight.with_status(FlightStatus.DELAYED, "NEW TIME 10:00")
        assert flight.status is FlightStatus.ON_TIME
        assert updated.status is FlightStatus.DELAYED
        assert updated.remark == "NEW TIME 10:00"


class TestStaticFlightProvider:
    def test_board_is_sorted_and_in_the_future(self) -> None:
        now = datetime(2026, 7, 16, 8, 0)
        flights = StaticFlightProvider().fetch(now, BoardKind.DEPARTURES)
        assert flights
        assert list(flights) == sorted(flights, key=lambda f: f.sort_key)
        assert all(f.scheduled >= now - timedelta(minutes=13) for f in flights)

    def test_schedule_rolls_forward_forever(self) -> None:
        provider = StaticFlightProvider()
        far_future = datetime(2029, 1, 1, 3, 30)
        assert len(provider.fetch(far_future, BoardKind.DEPARTURES)) == 16

    def test_arrivals_are_not_served_yet(self) -> None:
        assert StaticFlightProvider().fetch(datetime.now(), BoardKind.ARRIVALS) == ()

    def test_status_follows_time_to_departure(self) -> None:
        entry = ScheduleEntry("CR999", "LONDON", "A01", 0)
        provider = StaticFlightProvider([entry], disruptions={})
        now = datetime(2026, 7, 16, 8, 0)
        # The single entry is scheduled 10 minutes before ``now`` + rolling.
        flight = provider.fetch(now, BoardKind.DEPARTURES)[0]
        assert flight.status in tuple(FlightStatus)

    def test_delay_carries_a_remark(self) -> None:
        entry = ScheduleEntry("CR777", "PARIS", "B02", 120)
        provider = StaticFlightProvider([entry], disruptions={"CR777": 45})
        flight = provider.fetch(datetime(2026, 7, 16, 8, 0), BoardKind.DEPARTURES)[0]
        assert flight.status is FlightStatus.DELAYED
        assert flight.remark.startswith("NEW TIME")


class _CountingProvider(FlightProvider):
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, now: datetime, board: BoardKind) -> tuple[Flight, ...]:
        self.calls += 1
        return (Flight("CR101", "NEW YORK", now, "A12", FlightStatus.ON_TIME),)


class _BrokenProvider(FlightProvider):
    def fetch(self, now: datetime, board: BoardKind) -> tuple[Flight, ...]:
        raise RuntimeError("upstream is on fire")


class TestFlightManager:
    def test_provider_is_called_once_per_refresh_window(self) -> None:
        provider = _CountingProvider()
        manager = FlightManager(provider, refresh_seconds=30)
        start = datetime(2026, 7, 16, 8, 0)
        for offset in range(0, 29):
            manager.current_flights(start + timedelta(seconds=offset))
        assert provider.calls == 1
        manager.current_flights(start + timedelta(seconds=31))
        assert provider.calls == 2

    def test_invalidate_forces_a_refresh(self) -> None:
        provider = _CountingProvider()
        manager = FlightManager(provider)
        now = datetime(2026, 7, 16, 8, 0)
        manager.current_flights(now)
        manager.invalidate()
        manager.current_flights(now)
        assert provider.calls == 2

    def test_broken_provider_never_propagates(self) -> None:
        manager = FlightManager(_BrokenProvider(), refresh_seconds=1)
        assert manager.current_flights(datetime.now()) == ()
