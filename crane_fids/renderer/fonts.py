"""Font resolution and caching.

Loading a TrueType face is expensive; at 30 FPS it must happen exactly once per
(family, size) pair.  :class:`FontRegistry` owns that cache and is the only
place in the code base allowed to touch the filesystem for fonts.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Final

from PIL import ImageFont

__all__ = ["FontRegistry", "FontWeight"]

_LOG = logging.getLogger(__name__)


class FontWeight(StrEnum):
    """The two weights an airport board actually needs."""

    REGULAR = "regular"
    BOLD = "bold"


#: Candidate file names, in order of preference.  The first entry of each list
#: is what a bundled asset should be called; the rest are the usual Linux /
#: Debian system fonts, which is what the Docker image installs.
_CANDIDATES: Final[dict[FontWeight, tuple[str, ...]]] = {
    FontWeight.BOLD: (
        "FIDS-Bold.ttf",
        "Inter-Bold.ttf",
        "Roboto-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf",
        "NotoSans-Bold.ttf",
    ),
    FontWeight.REGULAR: (
        "FIDS-Regular.ttf",
        "Inter-Regular.ttf",
        "Roboto-Regular.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
        "NotoSans-Regular.ttf",
    ),
}

#: Directories scanned after the caller supplied ``font_dir``.
_SYSTEM_FONT_DIRS: Final[tuple[Path, ...]] = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts"),
    Path("/Library/Fonts"),
    Path("C:/Windows/Fonts"),
)


class FontRegistry:
    """Resolve font families once, then hand out cached ``FreeTypeFont`` objects."""

    def __init__(self, font_dir: Path | None = None) -> None:
        self._search_dirs: tuple[Path, ...] = tuple(
            path for path in ((font_dir,) if font_dir else ()) + _SYSTEM_FONT_DIRS if path
        )
        self._resolved: dict[FontWeight, Path | None] = {
            weight: self._resolve(weight) for weight in FontWeight
        }
        for weight, path in self._resolved.items():
            if path is None:
                _LOG.warning(
                    "No TrueType font found for weight %s; falling back to the Pillow "
                    "bitmap font. Install fonts-dejavu or mount a font into %s.",
                    weight.value,
                    self._search_dirs[0] if self._search_dirs else "<none>",
                )
            else:
                _LOG.info("Font %s -> %s", weight.value, path)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get(self, size: int, weight: FontWeight = FontWeight.BOLD) -> ImageFont.ImageFont:
        """Return a cached font of ``size`` pixels for ``weight``."""
        path = self._resolved[weight]
        return _load(str(path) if path else None, max(int(size), 1))

    def bold(self, size: int) -> ImageFont.ImageFont:
        """Shorthand for ``get(size, FontWeight.BOLD)``."""
        return self.get(size, FontWeight.BOLD)

    def regular(self, size: int) -> ImageFont.ImageFont:
        """Shorthand for ``get(size, FontWeight.REGULAR)``."""
        return self.get(size, FontWeight.REGULAR)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _resolve(self, weight: FontWeight) -> Path | None:
        for name in _CANDIDATES[weight]:
            for directory in self._search_dirs:
                hit = _first_existing(directory, name)
                if hit is not None:
                    return hit
        return None


def _first_existing(directory: Path, name: str) -> Path | None:
    """Find ``name`` directly in ``directory`` or, failing that, anywhere below it."""
    try:
        if not directory.is_dir():
            return None
        direct = directory / name
        if direct.is_file():
            return direct
        matches: Iterable[Path] = directory.rglob(name)
        return next(iter(sorted(matches)), None)
    except OSError:  # pragma: no cover - unreadable mount points
        _LOG.debug("Font directory %s is not readable", directory, exc_info=True)
        return None


@lru_cache(maxsize=64)
def _load(path: str | None, size: int) -> ImageFont.ImageFont:
    """Load and memoise one font face.

    The cache is module level (and therefore process wide) on purpose: several
    layers ask for the same size and must share one face.
    """
    if path is None:
        return ImageFont.load_default(size=size)
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:  # pragma: no cover - corrupted font file
        _LOG.exception("Failed to load font %s at size %d; using default face", path, size)
        return ImageFont.load_default(size=size)
