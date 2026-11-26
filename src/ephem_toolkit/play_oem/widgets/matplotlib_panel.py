"""Composable wx panel for embedding Play-OEM Matplotlib figures."""

from __future__ import annotations

import math
from collections.abc import Callable

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ..matplotlib_helpers import CANVAS_INSET_DIP, _configure_figure_layout

ToolbarFactory = Callable[
    [FigureCanvasWxAgg],
    wx.Window,
]
"""Factory for an optional wx toolbar attached to a Matplotlib canvas."""

MINIMUM_CANVAS_WIDTH_DIP: int = 320
"""Smallest default canvas width in device-independent pixels."""

MINIMUM_CANVAS_HEIGHT_DIP: int = 240
"""Smallest default canvas height in device-independent pixels."""

MINIMUM_PREFERRED_HEIGHT_FRACTION: float = 0.6
"""Fraction of the preferred canvas height used as its minimum."""


class MatplotlibPanel(wx.Panel):
    """Own a Matplotlib canvas and optionally preserve its figure aspect."""

    def __init__(
        self,
        parent: wx.Window,
        figure: Figure,
        *,
        toolbar_factory: ToolbarFactory | None = None,
        preserve_aspect_ratio: bool = False,
        minimum_canvas_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self.figure = figure
        self.preserve_aspect_ratio = preserve_aspect_ratio
        _configure_figure_layout(figure)

        scale_factor = float(self.GetDPIScaleFactor())
        self.minimum_canvas_size = (
            _minimum_canvas_size(
                figure,
                scale_factor,
                preserve_aspect_ratio=preserve_aspect_ratio,
            )
            if minimum_canvas_size is None
            else minimum_canvas_size
        )
        _validate_canvas_size(self.minimum_canvas_size)
        self.preferred_canvas_size = _preferred_canvas_size(figure, scale_factor)

        self._canvas_host = wx.Panel(self, wx.ID_ANY)
        self.canvas = FigureCanvasWxAgg(
            self._canvas_host,
            wx.ID_ANY,
            figure,
        )
        self.canvas.SetMinSize(
            self.FromDIP(wx.Size(*self.minimum_canvas_size))
        )

        self.toolbar: wx.Window | None = None
        self._canvas_host_sizer = wx.BoxSizer(wx.VERTICAL)
        if toolbar_factory is not None:
            self.toolbar = toolbar_factory(self.canvas)
            if isinstance(self.toolbar, wx.ToolBar):
                self.toolbar.Realize()
            self._canvas_host_sizer.Add(self.toolbar, 0, wx.EXPAND)
        self._canvas_host.SetSizer(self._canvas_host_sizer)

        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer.Add(self._canvas_host, 1, wx.EXPAND)
        self.SetSizer(panel_sizer)

        inset = self.FromDIP(CANVAS_INSET_DIP)
        canvas_minimum = self.canvas.GetMinSize()
        self._canvas_host.SetMinSize(
            wx.Size(
                canvas_minimum.width + inset * 2,
                canvas_minimum.height + inset * 2,
            )
        )
        toolbar_height = (
            self.toolbar.GetBestSize().height if self.toolbar is not None else 0
        )
        self.SetMinSize(
            wx.Size(
                canvas_minimum.width + inset * 2,
                canvas_minimum.height + inset * 2 + toolbar_height,
            )
        )
        self._canvas_host.Bind(wx.EVT_SIZE, self._on_canvas_host_size)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_mousewheel)

    @property
    def preferred_size(self) -> wx.Size:
        """Return the preferred figure size plus inset and optional toolbar."""
        inset = self.FromDIP(CANVAS_INSET_DIP)
        toolbar_height = (
            self.toolbar.GetBestSize().height if self.toolbar is not None else 0
        )
        preferred = self.FromDIP(self.preferred_canvas_size)
        return wx.Size(
            preferred.width + inset * 2,
            preferred.height + inset * 2 + toolbar_height,
        )

    def _on_mousewheel(self, event: wx.MouseEvent) -> None:
        event.Skip()

    def _on_canvas_host_size(self, event: wx.SizeEvent) -> None:
        self._canvas_host.Layout()
        self._fit_canvas()
        event.Skip()

    def _fit_canvas(self) -> None:
        host_size = self._canvas_host.GetClientSize()
        inset = self._canvas_host.FromDIP(CANVAS_INSET_DIP)
        toolbar_height = 0
        if self.toolbar is not None:
            toolbar_position = self.toolbar.GetPosition()
            toolbar_height = toolbar_position.y + self.toolbar.GetSize().height
        bounds = _fit_canvas_bounds(
            host_size.width,
            host_size.height,
            (
                self.figure.get_figwidth() / self.figure.get_figheight()
                if self.preserve_aspect_ratio
                else None
            ),
            toolbar_height,
            inset,
        )
        if bounds is None:
            return
        x, y, width, height = bounds
        self.canvas.SetSize(wx.Size(width, height))
        self.canvas.Move(wx.Point(x, y))


def _minimum_canvas_size(
    figure: Figure,
    dpi_scale_factor: float,
    *,
    preserve_aspect_ratio: bool = False,
) -> tuple[int, int]:
    """Return canvas minimum dimensions in device-independent pixels."""
    if not math.isfinite(dpi_scale_factor) or dpi_scale_factor <= 0.0:
        raise ValueError("dpi_scale_factor must be a finite positive number")

    preferred_width, preferred_height = _figure_size_in_dips(
        figure, dpi_scale_factor
    )
    minimum_height = max(
        MINIMUM_CANVAS_HEIGHT_DIP,
        MINIMUM_PREFERRED_HEIGHT_FRACTION * preferred_height,
    )
    if not preserve_aspect_ratio:
        return MINIMUM_CANVAS_WIDTH_DIP, math.ceil(minimum_height)
    scale = max(
        MINIMUM_CANVAS_WIDTH_DIP / preferred_width,
        minimum_height / preferred_height,
    )
    return (
        math.ceil(preferred_width * scale),
        math.ceil(preferred_height * scale),
    )


def _preferred_canvas_size(figure: Figure, dpi_scale_factor: float) -> wx.Size:
    """Return preferred renderer dimensions converted to logical pixels."""
    width, height = _figure_size_in_dips(figure, dpi_scale_factor)
    return wx.Size(math.ceil(width), math.ceil(height))


def _figure_size_in_dips(
    figure: Figure,
    dpi_scale_factor: float,
) -> tuple[float, float]:
    """Convert the figure's physical renderer size to device-independent pixels."""
    width_inches, height_inches = figure.get_size_inches()
    width = float(width_inches) * figure.dpi / dpi_scale_factor
    height = float(height_inches) * figure.dpi / dpi_scale_factor
    if not all(math.isfinite(value) and value > 0.0 for value in (width, height)):
        raise ValueError("figure dimensions and dpi must be finite and positive")
    return width, height


def _validate_canvas_size(size: tuple[int, int]) -> None:
    if len(size) != 2 or any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in size
    ):
        raise ValueError("minimum_canvas_size must contain two positive integers")


def _fit_canvas_bounds(
    host_width: int,
    host_height: int,
    figure_aspect: float | None,
    toolbar_height: int,
    inset: int,
) -> tuple[int, int, int, int] | None:
    """Fit and center a figure-aspect canvas in the space below its toolbar."""
    if host_width <= 0 or host_height <= 0:
        return None
    available_width = host_width - 2 * inset
    available_height = host_height - toolbar_height - 2 * inset
    if available_width <= 0 or available_height <= 0:
        return None

    if figure_aspect is None:
        return inset, toolbar_height + inset, available_width, available_height

    width = min(available_width, math.floor(available_height * figure_aspect))
    height = min(available_height, math.floor(width / figure_aspect))
    x = inset + (available_width - width) // 2
    y = toolbar_height + inset + (available_height - height) // 2
    return x, y, width, height
