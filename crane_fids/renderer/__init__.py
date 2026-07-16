"""Frame composition layer (Pillow only, no OpenCV).

Public surface:

* :class:`~crane_fids.renderer.board.FidsRenderer` -- turns a
  :class:`~crane_fids.renderer.context.FrameContext` into a ``PIL.Image``.
* :class:`~crane_fids.renderer.context.FrameContext` -- the immutable snapshot
  the renderer draws.
* :class:`~crane_fids.renderer.theme.Theme` / ``Layout`` -- look and geometry.

Nothing in this package knows about FFmpeg, environment variables or where
flight data came from.
"""

from __future__ import annotations

from .board import FidsRenderer
from .context import FrameContext
from .fonts import FontRegistry
from .layers import Layer
from .theme import Layout, Theme

__all__ = [
    "FidsRenderer",
    "FontRegistry",
    "FrameContext",
    "Layer",
    "Layout",
    "Theme",
]
