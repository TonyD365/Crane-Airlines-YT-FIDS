"""Process entry point.

    python app.py             # start the broadcast (or dry-run without RTMP_URL)
    python app.py --preview   # write a single PNG frame and exit

This file contains no business logic: it reads the environment, builds the
object graph and hands control to :class:`crane_fids.application.Application`.
"""

from __future__ import annotations
from dotenv import load_dotenv


import argparse
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

from crane_fids import __version__
from crane_fids.application import build_application
from crane_fids.config import Config, ConfigError
from crane_fids.flight_manager import RandomisedStaticFlightProvider
from crane_fids.logging_setup import configure_logging
from crane_fids.models import BoardKind
from crane_fids.renderer import FidsRenderer, FrameContext

_LOG = logging.getLogger("crane_fids.app")

load_dotenv()

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
    now = datetime.now()
    flights = tuple(RandomisedStaticFlightProvider().fetch(now, BoardKind.DEPARTURES))
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

    return build_application(config).run()


if __name__ == "__main__":
    main()
