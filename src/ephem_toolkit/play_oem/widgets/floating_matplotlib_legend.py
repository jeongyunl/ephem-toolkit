"""Floating wx panel that sizes itself to a Matplotlib figure legend."""

from __future__ import annotations

import math
from collections.abc import Sequence

import wx
from matplotlib.artist import Artist
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ..matplotlib_helpers import (
    create_figure,
    create_figure_legend,
    legend_canvas_size_px,
)
from .floating_panel import FloatingPanel, PanelCorner, PanelInteraction

LEGEND_CANVAS_PADDING_PX: int = 2
"""Physical-pixel inset around a rendered floating legend."""


class FloatingMatplotlibLegend(FloatingPanel):
    """Floating legend panel with renderer-measured, DPI-aware canvas sizing."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        name: str = "Legend",
        handle_label: str = "≡",
        corner: PanelCorner = PanelCorner.TOP_RIGHT,
        interaction: PanelInteraction = PanelInteraction.HOVER,
        initially_expanded: bool = False,
        content_margin_dip: int = 0,
        popup_border_width_dip: int = 1,
    ) -> None:
        super().__init__(
            parent,
            name=name,
            handle_label=handle_label,
            corner=corner,
            interaction=interaction,
            initially_expanded=initially_expanded,
            content_margin_dip=content_margin_dip,
            popup_border_width_dip=popup_border_width_dip,
        )
        self.figure: Figure = create_figure(
            (1.0, 1.0),
            constrained_layout=False,
        )
        self.canvas = FigureCanvasWxAgg(
            self.GetContentWindow(),
            wx.ID_ANY,
            self.figure,
        )
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        content_sizer.Add(self.canvas, 1, wx.EXPAND)
        self.SetContentSizer(content_sizer)
        self.set_handles(())

    def set_handles(self, handles: Sequence[Artist]) -> None:
        """Replace legend entries and resize the canvas to their rendered bounds."""
        self.figure.clear()
        legend = create_figure_legend(self.figure, handles)
        self.canvas.draw()
        width_px, height_px = legend_canvas_size_px(
            legend,
            self.canvas.get_renderer(),
            padding_px=LEGEND_CANVAS_PADDING_PX,
        )
        self.figure.set_size_inches(
            width_px / self.figure.dpi,
            height_px / self.figure.dpi,
            forward=False,
        )
        dpi_scale = float(self.canvas.GetDPIScaleFactor())
        if not math.isfinite(dpi_scale) or dpi_scale <= 0.0:
            raise ValueError("canvas DPI scale factor must be finite and positive")
        self.canvas.SetMinSize(
            wx.Size(
                math.ceil(width_px / dpi_scale),
                math.ceil(height_px / dpi_scale),
            )
        )
        self.RefreshLayout()
        self.canvas.draw_idle()
