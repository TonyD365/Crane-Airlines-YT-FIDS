"""Drawing layers.

A layer is a small, independent unit of drawing that knows how to paint itself
onto a frame given a :class:`~crane_fids.renderer.context.FrameContext`.  The
board is nothing but an ordered list of layers, which is what makes future
features (logo, weather, advertising, an arrivals page) additive rather than
invasive: write a new layer, put it in the list, change nothing else.

Layers are split in two families:

* ``is_static`` layers depend only on configuration and are painted **once**
  into a cached background image;
* dynamic layers are painted on every frame.

That split is the single most important performance decision in the renderer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Hashable, Sequence
from typing import Final

from PIL import Image, ImageDraw

from ..models import Flight
from .context import FrameContext
from .fonts import FontRegistry
from .theme import Column, Layout, Theme

__all__ = [
    "CachedRegionLayer",
    "ChromeLayer",
    "ClockLayer",
    "ColumnHeaderLayer",
    "FlightTableLayer",
    "HeaderLayer",
    "Layer",
    "PageIndicatorLayer",
    "TickerLayer",
]

_LOG = logging.getLogger(__name__)

_ELLIPSIS: Final[str] = "…"


class Layer(ABC):
    """Base class of every drawable board element."""

    #: Static layers are rendered once into the cached background.
    is_static: bool = False

    def __init__(self, theme: Theme, layout: Layout, fonts: FontRegistry) -> None:
        self._theme = theme
        self._layout = layout
        self._fonts = fonts

    @property
    def name(self) -> str:
        """Layer name, used in logs."""
        return type(self).__name__

    @abstractmethod
    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        """Paint this layer onto ``image``.

        Args:
            image: The frame being composed (RGB).
            draw: A draw handle bound to ``image``, shared by all layers.
            ctx: The frame snapshot.
        """


class CachedRegionLayer(Layer, ABC):
    """A layer that repaints only when its content actually changes.

    Text rasterisation is by far the most expensive operation in the renderer,
    yet almost nothing on an airport board changes 30 times per second: rows
    change when the timetable refreshes, the clock once per second, the
    blinkers twice.  Subclasses therefore expose a cheap :meth:`cache_key`; the
    region is re-rasterised only when that key changes and is otherwise pasted
    back verbatim.

    Contract: a cached region must not overlap the region of another dynamic
    layer, because the clean background is taken from the frame itself (which,
    at ``draw`` time, still holds the static background inside this region).
    """

    def __init__(self, theme: Theme, layout: Layout, fonts: FontRegistry) -> None:
        super().__init__(theme, layout, fonts)
        self._cache: Image.Image | None = None
        self._cache_key: Hashable = object()

    @abstractmethod
    def region(self) -> tuple[int, int, int, int]:
        """Return the ``(left, top, right, bottom)`` box owned by this layer."""

    @abstractmethod
    def cache_key(self, ctx: FrameContext) -> Hashable:
        """Return a value that changes exactly when the region must be repainted."""

    @abstractmethod
    def paint(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        """Paint the region onto ``image``, whose origin is the region's top-left."""

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        left, top, right, bottom = self.region()
        key = self.cache_key(ctx)
        if self._cache is None or key != self._cache_key:
            region = image.crop((left, top, right, bottom))
            self.paint(region, ImageDraw.Draw(region), ctx)
            self._cache = region
            self._cache_key = key
        image.paste(self._cache, (left, top))


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    """Shorten ``text`` with an ellipsis until it fits into ``max_width``."""
    if max_width <= 0 or not text:
        return text
    if draw.textlength(text, font=font) <= max_width:
        return text
    truncated = text
    while truncated and draw.textlength(truncated + _ELLIPSIS, font=font) > max_width:
        truncated = truncated[:-1]
    return (truncated + _ELLIPSIS) if truncated else ""


def dim(colour: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Return ``colour`` scaled towards black by ``factor`` (0..1)."""
    return tuple(max(0, min(255, int(channel * factor))) for channel in colour)  # type: ignore[return-value]


# ---------------------------------------------------------------------- #
# Static layers
# ---------------------------------------------------------------------- #
class ChromeLayer(Layer):
    """Background bands: header, column header strip, ticker bar."""

    is_static = True

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        layout, theme = self._layout, self._theme
        draw.rectangle((0, 0, layout.width, layout.height), fill=theme.background)

        # Header band with its accent underline.
        draw.rectangle((0, 0, layout.width, layout.header_height), fill=theme.header_background)
        accent = max(3, layout.height // 270)
        draw.rectangle(
            (0, layout.header_height - accent, layout.width, layout.header_height),
            fill=theme.header_accent,
        )

        # Column header band.
        draw.rectangle(
            (
                0,
                layout.column_header_top,
                layout.width,
                layout.column_header_top + layout.column_header_height,
            ),
            fill=theme.column_header_background,
        )

        # Ticker band.
        draw.rectangle(
            (0, layout.ticker_top, layout.width, layout.height), fill=theme.ticker_background
        )
        draw.line(
            (0, layout.ticker_top, layout.width, layout.ticker_top),
            fill=theme.row_separator,
            width=2,
        )


class HeaderLayer(Layer):
    """Airline name and board title."""

    is_static = True

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        layout, theme = self._layout, self._theme
        centre_y = layout.header_height // 2

        airline_font = self._fonts.bold(layout.airline_font_size)
        title_font = self._fonts.bold(layout.board_title_font_size)

        # Yellow accent block in front of the airline name: a cheap, very
        # recognisable "airport signage" cue.
        block_width = max(6, layout.width // 240)
        block_top = centre_y - int(layout.header_height * 0.28)
        block_bottom = centre_y + int(layout.header_height * 0.28)
        draw.rectangle(
            (layout.margin, block_top, layout.margin + block_width, block_bottom),
            fill=theme.header_accent,
        )

        text_x = layout.margin + block_width + int(layout.width * 0.012)
        draw.text(
            (text_x, centre_y),
            ctx.airline_name.upper(),
            font=airline_font,
            fill=theme.header_text,
            anchor="lm",
        )
        draw.text(
            (layout.width // 2, centre_y),
            ctx.board_title.upper(),
            font=title_font,
            fill=theme.board_title,
            anchor="mm",
        )


class ColumnHeaderLayer(Layer):
    """The ``TIME  FLIGHT  DESTINATION  DEPARTURE  GATE  STATUS`` strip."""

    is_static = True

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        layout, theme = self._layout, self._theme
        font = self._fonts.bold(layout.column_header_font_size)
        centre_y = layout.column_header_top + layout.column_header_height // 2
        for column in layout.columns:
            x, anchor = layout.anchor_x(column)
            draw.text(
                (x, centre_y), column.title, font=font, fill=theme.column_header_text, anchor=anchor
            )


# ---------------------------------------------------------------------- #
# Dynamic layers
# ---------------------------------------------------------------------- #
class ClockLayer(CachedRegionLayer):
    """Right-aligned header clock: ``HH:MM`` with blinking colon plus seconds.

    Repainted twice per second (the colon), never more.
    """

    #: Half a second, in microseconds: the colon is lit during the first half
    #: of every second, like an airport master clock.
    _COLON_ON_UNTIL_US: Final[int] = 500_000

    def _colon_is_lit(self, ctx: FrameContext) -> bool:
        """Whether the ``HH:MM`` separator is currently visible."""
        return ctx.now.microsecond < self._COLON_ON_UNTIL_US

    def region(self) -> tuple[int, int, int, int]:
        layout = self._layout
        return (layout.width - int(layout.width * 0.30), 0, layout.width, layout.header_height)

    def cache_key(self, ctx: FrameContext) -> Hashable:
        return (ctx.now.strftime("%a %d %b %H:%M:%S"), self._colon_is_lit(ctx))

    def paint(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        layout, theme = self._layout, self._theme
        clock_font = self._fonts.bold(layout.clock_font_size)
        seconds_font = self._fonts.bold(layout.clock_seconds_font_size)
        caption_font = self._fonts.regular(layout.subtitle_font_size)

        right = image.width - layout.margin
        centre_y = layout.header_height // 2

        seconds_text = ctx.now.strftime("%S")
        seconds_width = draw.textlength(seconds_text, font=seconds_font)
        gap = int(layout.width * 0.005)

        draw.text(
            (right, centre_y - int(layout.header_height * 0.06)),
            seconds_text,
            font=seconds_font,
            fill=theme.clock_seconds,
            anchor="rm",
        )

        separator = ":" if self._colon_is_lit(ctx) else " "
        hhmm = f"{ctx.now:%H}{separator}{ctx.now:%M}"
        draw.text(
            (right - seconds_width - gap, centre_y - int(layout.header_height * 0.08)),
            hhmm,
            font=clock_font,
            fill=theme.clock_text,
            anchor="rm",
        )
        draw.text(
            (right, centre_y + int(layout.header_height * 0.26)),
            f"{ctx.timezone_label}  {ctx.now:%a %d %b}".upper(),
            font=caption_font,
            fill=theme.muted_text,
            anchor="rm",
        )


class FlightTableLayer(Layer):
    """The flight rows of the current page.

    This layer draws variable-height rows directly onto the frame. It does not
    cache because row heights change based on text content, making the cache
    key complex. The performance impact is minimal since text rasterisation
    is already the dominant cost.
    """

    #: Blink frequency of BOARDING / FINAL CALL statuses, in hertz.
    BLINK_HZ: Final[float] = 1.0
    #: How dark a blinking status gets in its "off" phase (never fully black:
    #: a hard on/off flicker is unreadable after video compression).
    BLINK_OFF_FACTOR: Final[float] = 0.22
    #: Scroll speed in pixels per second
    SCROLL_SPEED: Final[float] = 120.0

    def __init__(self, theme: Theme, layout: Layout, fonts: FontRegistry) -> None:
        super().__init__(theme, layout, fonts)
        self._scroll_positions: dict[tuple[int, int], float] = {}  # (row_index, col_index) -> position
        self._scroll_directions: dict[tuple[int, int], int] = {}  # (row_index, col_index) -> direction (1 or -1)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        """Paint the flight table directly onto the image."""
        self.paint(image, draw, ctx)

    def paint(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        flights = ctx.page_flights
        if not flights:
            self._draw_empty(draw, image, ctx)
            return
        blink_on = ctx.blink_on(self.BLINK_HZ)
        layout = self._layout
        theme = self._theme
        
        # Calculate row heights and positions
        row_heights = []
        for flight in flights:
            height = self._calculate_row_height(draw, flight, layout)
            row_heights.append(height)
        
        # Draw row backgrounds first (starting from rows_top, not 0)
        y_offset = layout.rows_top
        for index, row_height in enumerate(row_heights):
            # Draw zebra row background
            fill = theme.row_background_even if index % 2 else theme.row_background_odd
            draw.rectangle((0, y_offset, layout.width, y_offset + row_height), fill=fill)
            # Draw row separator
            draw.line((0, y_offset + row_height, layout.width, y_offset + row_height), 
                     fill=theme.row_separator, width=1)
            y_offset += row_height
        
        # Draw rows with variable heights (starting from rows_top)
        y_offset = layout.rows_top
        for index, (flight, row_height) in enumerate(zip(flights, row_heights)):
            self._draw_row(draw, image, index, flight, blink_on, y_offset, row_height, ctx)
            y_offset += row_height

    # ------------------------------------------------------------------ #
    # Internals -- all coordinates are local to the region
    # ------------------------------------------------------------------ #
    def _calculate_row_height(
        self, draw: ImageDraw.ImageDraw, flight: Flight, layout: Layout
    ) -> int:
        """Calculate the height needed for this row (always single line)."""
        return layout.row_height

    def _draw_row(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        index: int,
        flight: Flight,
        blink_on: bool,
        y_offset: int = 0,
        row_height: int | None = None,
        ctx: FrameContext | None = None,
    ) -> None:
        layout, theme = self._layout, self._theme
        if row_height is None:
            row_height = layout.row_height
        centre_y = y_offset + row_height // 2
        font = self._fonts.bold(layout.row_font_size)
        remark_font = self._fonts.regular(layout.remark_font_size)

        values: dict[str, tuple[str, tuple[int, int, int]]] = {
            "time": (flight.scheduled_label, theme.primary_text),
            "flight": (flight.flight_number, theme.highlight_text),
            "destination": (flight.destination.upper(), theme.primary_text),
            "departure": (flight.departure.upper(), theme.primary_text),
            "gate": (flight.gate, theme.primary_text),
            "status": (flight.status.label, flight.status.colour),
        }

        has_remark = bool(flight.remark)
        text_y = centre_y - int(row_height * 0.12) if has_remark else centre_y

        for col_index, column in enumerate(layout.columns):
            text, colour = values[column.key]
            if column.key == "status" and flight.status.blinking and not blink_on:
                colour = dim(colour, self.BLINK_OFF_FACTOR)
            self._draw_cell(draw, image, column, text, colour, font, text_y, index, col_index, ctx)

        if has_remark:
            column = self._column("destination")
            left, right = layout.column_box(column)
            remark_y = centre_y + int(row_height * 0.26)
            draw.text(
                (left, remark_y),
                fit_text(draw, flight.remark.upper(), remark_font, right - left),
                font=remark_font,
                fill=theme.remark_text,
                anchor="lm",
            )

    def _count_text_lines(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> int:
        """Count how many lines the text will need when wrapped."""
        if max_width <= 0 or not text:
            return 1
        if draw.textlength(text, font=font) <= max_width:
            return 1
        
        # Split text into words and calculate lines
        words = text.split()
        if not words:
            return 1
        
        lines = 0
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if draw.textlength(test_line, font=font) <= max_width:
                current_line = test_line
            else:
                lines += 1
                current_line = word
        if current_line:
            lines += 1
        
        return max(1, lines)

    def _draw_cell(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        column: Column,
        text: str,
        colour: tuple[int, int, int],
        font,
        y: int,
        row_index: int = 0,
        col_index: int = 0,
        ctx: FrameContext | None = None,
    ) -> None:
        layout = self._layout
        left, right = layout.column_box(column)
        x, anchor = layout.anchor_x(column)
        max_width = right - left
        
        if max_width <= 0:
            return
        
        # Check if text needs scrolling
        text_width = draw.textlength(text, font=font)
        if text_width > max_width and ctx is not None:
            # Text is too long - implement scrolling
            scroll_key = (row_index, col_index)
            
            # Initialize scroll position if needed
            if scroll_key not in self._scroll_positions:
                self._scroll_positions[scroll_key] = 0.0
                self._scroll_directions[scroll_key] = 1
            
            # Update scroll position
            current_pos = self._scroll_positions[scroll_key]
            direction = self._scroll_directions[scroll_key]
            
            # Move text
            current_pos += direction * self.SCROLL_SPEED * (1.0 / 30.0)  # Assuming 30 fps
            
            # Check bounds and reverse direction
            max_scroll = text_width - max_width
            if current_pos >= max_scroll:
                current_pos = max_scroll
                self._scroll_directions[scroll_key] = -1
            elif current_pos < 0:
                current_pos = 0
                self._scroll_directions[scroll_key] = 1
            
            self._scroll_positions[scroll_key] = current_pos
            
            # Draw scrolling text using clipping
            # Create a temporary image for the text
            text_img = Image.new("RGBA", (int(text_width) + 2, int(layout.row_height)), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)
            text_draw.text((0, layout.row_height // 2), text, font=font, fill=colour, anchor="lm")
            
            # Paste the text with offset
            image.paste(text_img.crop((int(current_pos), 0, int(current_pos) + max_width, layout.row_height)), 
                       (left, int(y - layout.row_height // 2)), text_img.crop((int(current_pos), 0, int(current_pos) + max_width, layout.row_height)))
        else:
            # Text fits, just draw it
            draw.text((x, y), fit_text(draw, text, font, max_width), font=font, fill=colour, anchor=anchor)

    def _column(self, key: str) -> Column:
        for column in self._layout.columns:
            if column.key == key:
                return column
        raise KeyError(f"No column named {key!r}")  # pragma: no cover - layout bug

    def _draw_empty(self, draw: ImageDraw.ImageDraw, image: Image.Image, ctx: FrameContext) -> None:
        layout, theme = self._layout, self._theme
        font = self._fonts.bold(layout.row_font_size)
        draw.text(
            (image.width // 2, image.height // 2),
            "NO SCHEDULED DEPARTURES",
            font=font,
            fill=theme.muted_text,
            anchor="mm",
        )
        _LOG.debug("Rendered empty board at %s", ctx.now.isoformat(timespec="seconds"))


class PageIndicatorLayer(CachedRegionLayer):
    """Small dots showing which page of the board is on screen."""

    def region(self) -> tuple[int, int, int, int]:
        layout = self._layout
        half = int(layout.width * 0.12)
        return (
            layout.width // 2 - half,
            layout.header_height - int(layout.header_height * 0.30),
            layout.width // 2 + half,
            layout.header_height,
        )

    def cache_key(self, ctx: FrameContext) -> Hashable:
        return (ctx.page_index, ctx.page_count)

    def paint(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        if ctx.page_count <= 1:
            return
        layout, theme = self._layout, self._theme
        radius = max(3, layout.height // 220)
        spacing = radius * 4
        total = ctx.page_count
        centre_x = image.width // 2
        y = int(layout.header_height * 0.16)
        start_x = centre_x - ((total - 1) * spacing) // 2
        for index in range(total):
            colour = (
                theme.page_indicator_active
                if index == ctx.page_index
                else theme.page_indicator_idle
            )
            x = start_x + index * spacing
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colour)


class TickerLayer(Layer):
    """Right-to-left scrolling welcome message.

    The message is rasterised **once** into a strip; every frame only pastes
    that strip at a shifted offset, which is orders of magnitude cheaper than
    re-drawing text and keeps the CPU budget at 1080p30 comfortable.
    """

    #: Scroll speed as a fraction of the frame width per second.
    SPEED_RATIO: Final[float] = 0.075

    def __init__(self, theme: Theme, layout: Layout, fonts: FontRegistry) -> None:
        super().__init__(theme, layout, fonts)
        self._strip: Image.Image | None = None
        self._strip_text: str | None = None

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw, ctx: FrameContext) -> None:
        text = ctx.ticker_text.strip()
        if not text:
            return
        strip = self._ensure_strip(text)
        layout = self._layout
        speed = layout.width * self.SPEED_RATIO
        offset = int((ctx.elapsed_seconds * speed) % strip.width)

        x = -offset
        while x < layout.width:
            image.paste(strip, (x, layout.ticker_top))
            x += strip.width

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _ensure_strip(self, text: str) -> Image.Image:
        if self._strip is not None and self._strip_text == text:
            return self._strip
        layout, theme = self._layout, self._theme
        font = self._fonts.bold(layout.ticker_font_size)
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        gap = int(layout.width * 0.06)
        text_width = int(probe.textlength(text, font=font))
        strip_width = max(text_width + gap, layout.width + gap)
        strip = Image.new("RGB", (strip_width, layout.ticker_height), theme.ticker_background)
        strip_draw = ImageDraw.Draw(strip)
        strip_draw.text(
            (0, layout.ticker_height // 2),
            text,
            font=font,
            fill=theme.ticker_text,
            anchor="lm",
        )
        self._strip = strip
        self._strip_text = text
        _LOG.info("Ticker strip rasterised: %dx%d px", strip.width, strip.height)
        return strip


def default_layers(theme: Theme, layout: Layout, fonts: FontRegistry) -> Sequence[Layer]:
    """Return the layer stack of the departures board, in painting order."""
    return (
        ChromeLayer(theme, layout, fonts),
        HeaderLayer(theme, layout, fonts),
        ColumnHeaderLayer(theme, layout, fonts),
        ClockLayer(theme, layout, fonts),
        FlightTableLayer(theme, layout, fonts),
        PageIndicatorLayer(theme, layout, fonts),
        TickerLayer(theme, layout, fonts),
    )
