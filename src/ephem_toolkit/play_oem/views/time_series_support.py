"""Reusable wx shell support for 2D time-series data_views."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ..data_view_panel import DATA_VIEW_PANEL_MIN_SIZE
from ..widgets import (
    FloatingPanel,
    MatplotlibPanel,
    PanelCorner,
    PanelInteraction,
)
from .compact_controls import compact_controls


class TimeSeriesWxPanelMixin:
    """Own native wx embedding and floating-panel lifecycle for time-series data_views."""

    def _initialize_time_series_wx(self) -> None:
        """Initialize wx-owned fields before constructing a time-series panel."""
        self._time_series_panel: wx.Panel | None = None
        self._time_series_plot_panel: MatplotlibPanel | None = None
        self._time_series_canvas: FigureCanvasWxAgg | None = None
        self._time_series_figure: Figure | None = None
        self._time_series_status_panel: FloatingPanel | None = None
        self._time_series_status_label: wx.StaticText | None = None
        self._time_series_floating_panels: list[FloatingPanel] = []
        self._time_series_canvas_callback_ids: list[int] = []

    def _create_time_series_panel(
        self,
        parent: wx.Window,
        figure: Figure,
        *,
        name: str | None = None,
        toolbar_factory: Callable[
            [FigureCanvasWxAgg],
            wx.Window,
        ]
        | None = None,
        preserve_aspect_ratio: bool = False,
    ) -> wx.Panel:
        """Create a minimum-size-aware native panel with a direct Matplotlib canvas."""
        if self._time_series_panel is not None:
            raise RuntimeError("time-series wx panel has already been created")

        panel = wx.Panel(parent, wx.ID_ANY)
        panel.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
        if name is not None:
            panel.SetName(name)
        panel.SetMinSize(panel.FromDIP(wx.Size(*DATA_VIEW_PANEL_MIN_SIZE)))

        plot_panel = MatplotlibPanel(
            panel,
            figure,
            toolbar_factory=toolbar_factory,
            preserve_aspect_ratio=preserve_aspect_ratio,
            minimum_canvas_size=DATA_VIEW_PANEL_MIN_SIZE,
        )
        canvas = plot_panel.canvas
        canvas.SetMinSize(canvas.FromDIP(wx.Size(*DATA_VIEW_PANEL_MIN_SIZE)))

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(plot_panel, 1, wx.EXPAND)
        panel.SetSizer(root)

        self._time_series_panel = panel
        self._time_series_plot_panel = plot_panel
        self._time_series_canvas = canvas
        self._time_series_figure = figure
        return panel

    def _create_time_series_floating_panel(
        self,
        parent: wx.Window,
        *,
        name: str,
        handle_label: str = "≡",
        corner: PanelCorner | str = PanelCorner.TOP_RIGHT,
        interaction: PanelInteraction | str = PanelInteraction.HOVER,
        initially_expanded: bool = False,
    ) -> FloatingPanel:
        """Create and register a floating surface for time-series controls/status."""
        floating = FloatingPanel(
            parent,
            name=name,
            handle_label=handle_label,
            corner=corner,
            interaction=interaction,
            initially_expanded=initially_expanded,
        )
        self._time_series_floating_panels.append(floating)
        return floating

    def _compact_time_series_controls(
        self,
        controls: Sequence[wx.Window],
    ) -> None:
        """Apply compact GTK styling only to the supplied choices/buttons."""
        compact_controls(tuple(controls))

    def _create_time_series_status_label(
        self,
        parent: wx.Window,
        *,
        name: str,
        initial_text: str = "",
    ) -> wx.StaticText:
        """Create a named status readout for a time-series panel."""
        label = wx.StaticText(parent, wx.ID_ANY, initial_text)
        label.SetName(name)
        return label

    def _create_time_series_status_panel(
        self,
        parent: wx.Window,
        *,
        name: str,
        initial_text: str = "",
    ) -> tuple[FloatingPanel, wx.StaticText]:
        """Create an expanded top-left live status readout like Ground Track."""
        panel = self._create_time_series_floating_panel(
            parent,
            name=name,
            corner=PanelCorner.TOP_LEFT,
            interaction=PanelInteraction.CLICK,
            initially_expanded=True,
        )
        label = self._create_time_series_status_label(
            panel.GetContentWindow(),
            name=f"{name} text",
            initial_text=initial_text,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.EXPAND)
        panel.SetContentSizer(sizer)
        self._time_series_status_panel = panel
        self._time_series_status_label = label
        return panel, label

    def _set_time_series_status(self, text: str) -> None:
        """Update the live top-left status readout."""
        if self._time_series_status_label is not None:
            self._time_series_status_label.SetLabel(text)

    def _connect_time_series_canvas_event(
        self,
        event_name: str,
        callback: Callable[..., Any],
    ) -> int:
        """Connect and track one Matplotlib canvas callback for close cleanup."""
        canvas = self._time_series_canvas
        if canvas is None:
            raise RuntimeError("time-series canvas has not been created")
        callback_id = canvas.mpl_connect(event_name, callback)
        self._time_series_canvas_callback_ids.append(callback_id)
        return callback_id

    def _close_time_series_wx(self) -> None:
        """Close floating surfaces, disconnect canvas callbacks, and clear wx refs."""
        canvas = self._time_series_canvas
        if canvas is not None:
            for callback_id in self._time_series_canvas_callback_ids:
                canvas.mpl_disconnect(callback_id)
        self._time_series_canvas_callback_ids.clear()

        for floating in tuple(self._time_series_floating_panels):
            floating.Close()
        self._time_series_floating_panels.clear()

        self._time_series_panel = None
        self._time_series_plot_panel = None
        self._time_series_canvas = None
        self._time_series_figure = None
        self._time_series_status_panel = None
        self._time_series_status_label = None
