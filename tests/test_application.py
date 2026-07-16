"""Tests for the orchestration loop.

The loop is exercised with fakes only: no FFmpeg, no real clock rate, no
network.  What matters here is the resilience contract -- the loop must keep
running whatever its collaborators do.
"""

from __future__ import annotations

import threading
from datetime import datetime

from crane_fids.application import Application, LoopStats, build_application
from crane_fids.config import Config
from crane_fids.flight_manager import FlightManager, StaticFlightProvider
from crane_fids.renderer import FidsRenderer
from crane_fids.stream_engine import NullStreamEngine, StreamEngine

_ENV = {"WIDTH": "640", "HEIGHT": "360", "FPS": "30", "ROWS_PER_PAGE": "4"}


class _RecordingEngine(StreamEngine):
    def __init__(self, fail_after: int | None = None) -> None:
        self.frames = 0
        self.started = False
        self.stopped = False
        self._fail_after = fail_after

    def start(self) -> None:
        self.started = True

    def write(self, frame: bytes) -> bool:
        self.frames += 1
        if self._fail_after is not None and self.frames > self._fail_after:
            raise RuntimeError("engine exploded")
        return True

    def stop(self) -> None:
        self.stopped = True

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped


def _application(engine: StreamEngine) -> Application:
    config = Config.from_env(_ENV)
    manager = FlightManager(StaticFlightProvider(), refresh_seconds=30)
    renderer = FidsRenderer.from_config(config)
    return Application(config, manager, renderer, engine)


def _run_briefly(app: Application, seconds: float = 0.3) -> int:
    threading.Timer(seconds, app.request_stop).start()
    return app.run()


class TestApplication:
    def test_clean_run_writes_frames_and_stops_the_engine(self) -> None:
        engine = _RecordingEngine()
        app = _application(engine)
        assert _run_briefly(app) == 0
        assert engine.started and engine.stopped
        assert engine.frames > 0

    def test_engine_failures_do_not_stop_the_loop(self) -> None:
        engine = _RecordingEngine(fail_after=1)
        app = _application(engine)
        assert _run_briefly(app) == 0
        assert engine.frames > 2  # the loop kept going after the exception
        assert engine.stopped

    def test_broken_flight_manager_does_not_stop_the_loop(self) -> None:
        class _BrokenManager(FlightManager):
            def current_flights(self, now: datetime) -> tuple:  # type: ignore[override]
                raise RuntimeError("no data")

        config = Config.from_env(_ENV)
        engine = _RecordingEngine()
        app = Application(
            config,
            _BrokenManager(StaticFlightProvider()),
            FidsRenderer.from_config(config),
            engine,
        )
        assert _run_briefly(app) == 0
        assert engine.stopped

    def test_dry_run_composition_root(self) -> None:
        app = build_application(Config.from_env(_ENV))
        assert isinstance(app._engine, NullStreamEngine)  # no RTMP_URL -> dry run
        assert _run_briefly(app) == 0


class TestLoopStats:
    def test_summary_and_reset(self) -> None:
        stats = LoopStats()
        stats.frames_rendered = 30
        stats.render_seconds = 0.3
        summary = stats.summary(30)
        assert "frames=30" in summary and "render_avg=10.0ms" in summary
        stats.reset_window()
        assert stats.frames_rendered == 0
