"""The board renderer.

:class:`FidsRenderer` owns the frame buffer and the layer stack.  It knows
nothing about flights beyond the :class:`FrameContext` it is handed, and
nothing at all about FFmpeg -- it returns a Pillow image, full stop.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PIL import Image, ImageDraw

from ..config import Config
from .context import FrameContext
from .fonts import FontRegistry
from .layers import Layer, default_layers
from .theme import Layout, Theme

__all__ = ["FidsRenderer"]

_LOG = logging.getLogger(__name__)


class FidsRenderer:
    """Compose one departure board frame per call.

    Performance contract (this is a 30 FPS, 24x7 process):

    * fonts are loaded once, by :class:`FontRegistry`;
    * static layers are painted once into a cached background;
    * the returned image is a **reused buffer** -- it is valid until the next
      :meth:`render` call.  Callers that need to keep a frame must copy it.
    """

    def __init__(
        self,
        size: tuple[int, int],
        *,
        theme: Theme | None = None,
        layout: Layout | None = None,
        fonts: FontRegistry | None = None,
        layers: Sequence[Layer] | None = None,
        rows_per_page: int = 10,
    ) -> None:
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid frame size: {size}")

        self._size = (width, height)
        self._theme = theme or Theme()
        self._layout = layout or Layout(width=width, height=height, rows_per_page=rows_per_page)
        self._fonts = fonts or FontRegistry()
        self._layers = tuple(
            layers if layers is not None else default_layers(self._theme, self._layout, self._fonts)
        )

        self._background: Image.Image | None = None
        self._frame = Image.new("RGB", self._size, self._theme.background)
        self._draw = ImageDraw.Draw(self._frame)
        self._failed_layers: set[str] = set()

    # ------------------------------------------------------------------ #
    # Factories
    # ------------------------------------------------------------------ #
    @classmethod
    def from_config(cls, config: Config) -> FidsRenderer:
        """Build a renderer wired to ``config``."""
        theme = Theme()
        layout = Layout(
            width=config.video.width,
            height=config.video.height,
            rows_per_page=config.rows_per_page,
        )
        fonts = FontRegistry(config.font_dir)
        return cls(
            config.video.size,
            theme=theme,
            layout=layout,
            fonts=fonts,
            layers=default_layers(theme, layout, fonts),
        )

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def size(self) -> tuple[int, int]:
        """Frame size as ``(width, height)``."""
        return self._size

    @property
    def layout(self) -> Layout:
        """The geometry this renderer draws with."""
        return self._layout

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self, ctx: FrameContext) -> Image.Image:
        """Render one frame and return the (reused) buffer."""
        background = self._ensure_background(ctx)
        self._frame.paste(background, (0, 0))
        for layer in self._layers:
            if layer.is_static:
                continue
            self._safe_draw(layer, self._frame, self._draw, ctx)
        return self._frame

    def render_bytes(self, ctx: FrameContext) -> bytes:
        """Render one frame and return raw RGB24 bytes, ready for FFmpeg."""
        return self.render(ctx).tobytes()

    def invalidate_background(self) -> None:
        """Drop the cached static background (e.g. after a theme change)."""
        self._background = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _ensure_background(self, ctx: FrameContext) -> Image.Image:
        """Paint the static layers once.

        Static layers read only configuration-derived fields of ``ctx``
        (airline name, board title...), which never change during a process
        lifetime; that is what makes caching them sound.
        """
        if self._background is not None:
            return self._background
        background = Image.new("RGB", self._size, self._theme.background)
        draw = ImageDraw.Draw(background)
        for layer in self._layers:
            if layer.is_static:
                self._safe_draw(layer, background, draw, ctx)
        self._background = background
        _LOG.info(
            "Static background cached (%dx%d, %d static layers)",
            self._size[0],
            self._size[1],
            sum(1 for layer in self._layers if layer.is_static),
        )
        return background

    def _safe_draw(
        self,
        layer: Layer,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        ctx: FrameContext,
    ) -> None:
        """Run one layer, isolating the stream from its failures.

        A broken layer degrades the board; it must never stop the broadcast.
        The traceback is logged once per layer to keep the log readable.
        """
        try:
            layer.draw(image, draw, ctx)
        except Exception:
            if layer.name not in self._failed_layers:
                self._failed_layers.add(layer.name)
                _LOG.exception("Layer %s failed and will be skipped when it errors", layer.name)
