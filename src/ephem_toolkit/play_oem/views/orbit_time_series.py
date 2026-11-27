"""Shared wx shell wrapper for migrated orbit time-series data_views."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import wx
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import time_unit
from ..time_range import ResolvedTimeRange
from ..widgets import FloatingMatplotlibLegend, PanelCorner, PanelInteraction
from .data_view_base import (
    StoreTimeSeriesView,
    StoreViewContext,
    TimeSeriesWxPanelMixin,
)
from .data_view_registry import DataViewSpecMixin


class OrbitTimeSeriesView(
    DataViewSpecMixin,
    TimeSeriesWxPanelMixin,
    StoreTimeSeriesView,
):
    """Shared wx/store presentation for a standard time-series view implementation."""

    seek_on_click: bool = True

    def __init__(
        self,
        start_time_s: float,
        panel: wx.Window | None = None,
        on_seek: Callable[[float], None] | None = None,
    ) -> None:
        self._initialize_store_time_series(start_time_s)
        self._initialize_time_series_wx()
        self._parent = panel
        self._on_seek = on_seek
        self._legend_panel: FloatingMatplotlibLegend | None = None

    @property
    def status_label(self) -> str:
        return self.label

    def _present_figure(
        self,
        figure: Figure,
        *,
        start_time_s: float,
        display_time_unit: time_unit.TimeUnit,
    ) -> Figure | wx.Window:
        self._figure = figure
        axes = tuple(figure.axes)
        self._configure_time_series_axes(
            axes,
            start_time_s=start_time_s,
            time_unit=display_time_unit,
        )

        if self._parent is None:
            return figure

        panel = self._create_time_series_panel(
            self._parent,
            figure,
            name=f"{self.label} view",
            toolbar_factory=NavigationToolbar2WxAgg,
        )
        self._create_time_series_status_panel(
            panel,
            name=f"{self.status_label} status",
            initial_text=f"{self.status_label}: --",
        )
        self._legend_panel = FloatingMatplotlibLegend(
            panel,
            name=f"{self.label} legend",
            corner=PanelCorner.BOTTOM_RIGHT,
            interaction=PanelInteraction.HOVER,
            initially_expanded=False,
        )
        handles = self._legend_handles(axes)
        self._legend_panel.set_handles(handles)
        self._time_series_floating_panels.append(self._legend_panel)

        canvas = self._time_series_canvas
        if canvas is not None:
            self._connect_time_series_canvas_event(
                "button_press_event",
                self._on_canvas_click,
            )
        self.update(float(getattr(self, "_last_cursor_time_s", start_time_s)))
        return panel

    def _legend_handles(self, axes: tuple[Axes, ...]) -> tuple[Artist, ...]:
        handles: list[Artist] = []
        seen: set[tuple[str, str]] = set()
        for axis in axes:
            legend = getattr(axis, "get_legend", lambda: None)()
            if legend is not None:
                legend.remove()
            for artist in axis.lines:
                if not isinstance(artist, Line2D):
                    continue
                label = artist.get_label()
                if not label or label.startswith("_"):
                    continue
                key = (label, artist.get_color())
                if key not in seen:
                    seen.add(key)
                    handles.append(artist)
        return tuple(handles)

    def _on_canvas_click(self, event: Any) -> None:
        if event.inaxes is None or self._on_seek is None:
            return
        toolbar = getattr(self._time_series_plot_panel, "toolbar", None)
        if toolbar is not None and getattr(toolbar, "mode", ""):
            return
        if not getattr(event.inaxes, "_play_oem_seek_enabled", True):
            return
        axis_value = float(event.xdata)
        absolute_s = self._absolute_time_from_axis(axis_value)
        self._on_seek(absolute_s)

    def update_from_store(self, context: StoreViewContext) -> None:
        if self._store_context is None:
            raise RuntimeError(f"{self.label} view was not built from a store")
        self._prepare_store_context(context)
        if self._figure is not None:
            self._configure_time_series_axes(
                tuple(self._figure.axes),
                start_time_s=float(context.coverage[0]),
                time_unit=context.time_unit,
            )
        self.update(float(getattr(self, "_last_cursor_time_s", context.coverage[0])))

    def update(self, time_s: float) -> None:
        self._update_store_or_legacy_cursor(time_s)
        if self._time_series_status_label is not None:
            axis_time = self._axis_time(time_s)
            values: list[str] = []
            for axis in tuple(getattr(self._figure, "axes", ())):
                candidates: list[tuple[str, float]] = []
                for artist in axis.lines:
                    if not isinstance(artist, Line2D):
                        continue
                    label = artist.get_label()
                    if not label or label.startswith("_"):
                        continue
                    xs = np.asarray(artist.get_xdata(), dtype=float)
                    ys = np.asarray(artist.get_ydata(), dtype=float)
                    if xs.size == 0 or ys.size == 0:
                        continue
                    if xs.size != ys.size:
                        continue
                    index = int(np.argmin(np.abs(xs - axis_time)))
                    candidates.append((label, float(ys[index])))
                if candidates:
                    for label, value in candidates[:2]:
                        values.append(f"{label}: {value:.3g}")
            text = f"{self.status_label}: " + (" | ".join(values) if values else "--")
            self._set_time_series_status(text)

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        if self._store_context is not None:
            self._store_context = self._store_context_for_range(bounds, coverage)
        super().set_time_range(bounds, coverage)

    def consume_cursor_only_update(self) -> bool:
        return super().consume_cursor_only_update()

    def close(self) -> None:
        self._close_time_series_wx()
        self._legend_panel = None
        self._close_store_time_series()
