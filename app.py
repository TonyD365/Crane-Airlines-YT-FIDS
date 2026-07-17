"""Process entry point.

    python app.py             # start the broadcast (or dry-run without RTMP_URL)
    python app.py --preview   # write a single PNG frame and exit

This file contains no business logic: it reads the environment, builds the
object graph and hands control to :class:`crane_fids.application.Application`.

External code can import this module and update flights at runtime::

    import app
    from crane_fids import Flight, FlightStatus
    from datetime import datetime

    app.provider.set_flights([
        Flight("CR999", "DUBAI", datetime(2025, 7, 17, 14, 30), "F01", FlightStatus.ON_TIME),
    ])
"""

from __future__ import annotations
from dotenv import load_dotenv


import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import crane_fids
from crane_fids import __version__, BoardKind, Flight, FlightStatus
from crane_fids.application import build_application
from crane_fids.config import Config, ConfigError
from crane_fids.logging_setup import configure_logging
from crane_fids.renderer import FidsRenderer, FrameContext

_LOG = logging.getLogger("crane_fids.app")

load_dotenv()

# ------------------------------------------------------------------ #
# Default example flights shown when the board starts
# ------------------------------------------------------------------ #
def _default_flights() -> list[Flight]:
    """Return a handful of example flights for the current time."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    base = now + timedelta(minutes=5)  # first flight 5 minutes from now
    return [
        Flight("CR101", "NEW YORK",     base,                          "A12", FlightStatus.ON_TIME,     departure="NEWARK"),
        Flight("CR102", "CHICAGO",      base + timedelta(minutes=15),  "B08", FlightStatus.ON_TIME,     departure="CHICAGO"),
        Flight("CR103", "TORONTO",      base + timedelta(minutes=30),  "C11", FlightStatus.GATE_OPEN,   departure="TORONTO"),
        Flight("CR201", "VANCOUVER",    base + timedelta(minutes=45),  "D09", FlightStatus.BOARDING,    departure="VANCOUVER"),
        Flight("CR301", "LONDON",       base + timedelta(minutes=60),  "E73", FlightStatus.ON_TIME,     departure="LONDON"),
        Flight("CR401", "PARIS",        base + timedelta(minutes=75),  "A12", FlightStatus.LAST_CALL,   departure="PARIS"),
        Flight("CR118", "FRANKFURT",    base + timedelta(minutes=90),  "B08", FlightStatus.DELAYED,     departure="FRANKFURT",
               remark="NEW TIME " + (base + timedelta(minutes=105)).strftime("%H:%M")),
        Flight("CR233", "TOKYO",        base + timedelta(minutes=105), "C11", FlightStatus.ON_TIME,     departure="TOKYO"),
        Flight("CR507", "SHANGHAI",     base + timedelta(minutes=120), "D09", FlightStatus.FINAL_CALL,  departure="SHANGHAI"),
        Flight("CR612", "BEIJING",      base + timedelta(minutes=135), "E73", FlightStatus.ON_TIME,     departure="BEIJING"),
        Flight("CR715", "SINGAPORE",    base + timedelta(minutes=150), "A12", FlightStatus.ON_TIME,     departure="SINGAPORE"),
        Flight("CR808", "SYDNEY",       base + timedelta(minutes=165), "B08", FlightStatus.CANCELLED,   departure="SYDNEY"),
    ]


# ------------------------------------------------------------------ #
# Use the global provider from crane_fids module
# ------------------------------------------------------------------ #
provider = crane_fids._provider
crane_fids.set_flights(_default_flights())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crane-fids",
        description="Crane Airlines airport FIDS renderer and RTMP broadcaster.",
    )
    parser.add_argument("--version", action="version", version=f"crane-fids {__version__}")
    parser.add_argument(
        "--preview",
        metavar="PATH",
        nargs="?",
        const="preview.png",
        help="Render one frame to PATH (default: preview.png) and exit.",
    )
    parser.add_argument(
        "--preview-seconds",
        type=float,
        default=0.0,
        help="Stream time of the previewed frame, in seconds (affects blink/scroll phase).",
    )
    return parser.parse_args(argv)


def _run_preview(config: Config, path: Path, seconds: float) -> int:
    """Render a single frame to disk: the fastest way to review a layout."""
    now = datetime.now(timezone.utc)
    flights = tuple(provider.fetch(now, BoardKind.DEPARTURES))
    renderer = FidsRenderer.from_config(config)
    ctx = FrameContext(
        now=now,
        frame_index=int(seconds * config.video.fps),
        fps=config.video.fps,
        flights=flights,
        airline_name=config.airline_name,
        airport_name=config.airport_name,
        board_title=config.board_title,
        ticker_text=config.ticker_text,
        timezone_label=config.timezone_label,
        rows_per_page=config.rows_per_page,
        page_seconds=config.page_seconds,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    renderer.render(ctx).save(path)
    _LOG.info("Preview written to %s (%d flights)", path, len(flights))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Program entry point.  Returns a POSIX exit code."""
    args = _parse_args(argv)
    try:
        config = Config.from_env()
    except ConfigError as exc:
        configure_logging("INFO")
        _LOG.error("Invalid configuration: %s", exc)
        return 2

    configure_logging(config.log_level)
    _LOG.info("crane-fids %s", __version__)

    if args.preview:
        return _run_preview(config, Path(args.preview), args.preview_seconds)

    return build_application(config, provider=provider).run()


if __name__ == "__main__":
    main()