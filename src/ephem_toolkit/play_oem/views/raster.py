"""Matplotlib figure rasterization for legacy Tk display."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backend_bases import RendererBase
from matplotlib.figure import Figure
from matplotlib.lines import Line2D


@dataclass(frozen=True)
class RasterPanel:
    """Plot bounds and time range for one panel in a raster figure."""

    plot_left: int
    plot_right: int
    plot_top: int
    plot_bottom: int
    x_start: float
    x_end: float

    def cursor_column(self, elapsed_time: float) -> int:
        if self.x_start == self.x_end:
            return (self.plot_left + self.plot_right) // 2
        fraction = (elapsed_time - self.x_start) / (self.x_end - self.x_start)
        fraction = min(max(fraction, 0.0), 1.0)
        return round(self.plot_left + fraction * (self.plot_right - self.plot_left))

    def elapsed_at(self, pixel_x: int) -> float:
        if self.plot_left == self.plot_right or self.x_start == self.x_end:
            return self.x_start
        fraction = (pixel_x - self.plot_left) / (self.plot_right - self.plot_left)
        fraction = min(max(fraction, 0.0), 1.0)
        return self.x_start + fraction * (self.x_end - self.x_start)

    def contains_plot_point(self, pixel_x: int, pixel_y: int) -> bool:
        return (
            self.plot_left <= pixel_x <= self.plot_right
            and self.plot_top <= pixel_y <= self.plot_bottom
        )


@dataclass(frozen=True)
class RasterImage:
    """PPM pixels and per-axes coordinates for a Matplotlib figure."""

    width: int
    height: int
    ppm_data: bytes
    panels: tuple[RasterPanel, ...]


def render_matplotlib_raster(
    figure: Figure,
    axes: Sequence[Axes],
    cursor_artists: Sequence[Line2D],
) -> RasterImage:
    """Render a Matplotlib figure without cursor overlays for classic Tk."""
    cursor_visibility = tuple(
        cursor_artist.get_visible() for cursor_artist in cursor_artists
    )
    for cursor_artist in cursor_artists:
        cursor_artist.set_visible(False)
    try:
        canvas = FigureCanvasAgg(figure)
        canvas.draw()
        width, height = canvas.get_width_height()
        renderer = canvas.get_renderer()
        panels = tuple(
            _raster_panel(panel_axes, renderer, width, height) for panel_axes in axes
        )
        pixels = np.asarray(canvas.buffer_rgba(), dtype=np.uint8)[:, :, :3]
        ppm_header = f"P6\n{width} {height}\n255\n".encode("ascii")
        return RasterImage(
            width,
            height,
            ppm_header + np.ascontiguousarray(pixels).tobytes(),
            panels,
        )
    finally:
        for cursor_artist, visible in zip(cursor_artists, cursor_visibility):
            cursor_artist.set_visible(visible)


def _raster_panel(
    axes: Axes, renderer: RendererBase, width: int, height: int
) -> RasterPanel:
    bounds = axes.get_window_extent(renderer)
    x_start, x_end = axes.get_xlim()
    return RasterPanel(
        max(0, int(np.floor(bounds.x0))),
        min(width - 1, int(np.ceil(bounds.x1)) - 1),
        max(0, height - int(np.ceil(bounds.y1))),
        min(height - 1, height - int(np.floor(bounds.y0)) - 1),
        float(x_start),
        float(x_end),
    )
