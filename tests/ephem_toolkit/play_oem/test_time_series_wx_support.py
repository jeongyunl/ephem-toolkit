"""Tests for the shared wx shell used by 2D time-series views."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from matplotlib.figure import Figure

import wx

from ephem_toolkit.play_oem.views.base import TimeSeriesWxPanelMixin
from ephem_toolkit.play_oem.views.time_series_support import (
    TimeSeriesWxPanelMixin as DirectTimeSeriesWxPanelMixin,
)
from ephem_toolkit.play_oem.graph_panel import GRAPH_PANEL_MIN_SIZE


class _TimeSeriesWxSupport(TimeSeriesWxPanelMixin):
    pass


def test_time_series_wx_support_close_disconnects_and_clears_refs() -> None:
    support = _TimeSeriesWxSupport()
    support._initialize_time_series_wx()
    disconnected: list[int] = []
    support._time_series_canvas = SimpleNamespace(
        mpl_disconnect=lambda callback_id: disconnected.append(callback_id)
    )
    support._time_series_canvas_callback_ids = [11, 12]

    class Floating:
        def __init__(self) -> None:
            self.closed = False

        def Close(self, force: bool = False) -> bool:
            self.closed = True
            return True

    floating = Floating()
    support._time_series_floating_panels = [floating]
    support._time_series_panel = SimpleNamespace()
    support._time_series_plot_panel = SimpleNamespace()
    support._time_series_figure = Figure()

    support._close_time_series_wx()

    assert disconnected == [11, 12]
    assert floating.closed
    assert support._time_series_canvas_callback_ids == []
    assert support._time_series_floating_panels == []
    assert support._time_series_panel is None
    assert support._time_series_plot_panel is None
    assert support._time_series_canvas is None
    assert support._time_series_figure is None


@pytest.fixture
def wx_app() -> Any:
    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx display is not available")
    app = wx.App.Get() or wx.App(False)
    yield app


def test_time_series_wx_support_builds_minimum_canvas_shell(wx_app: Any) -> None:
    support = _TimeSeriesWxSupport()
    support._initialize_time_series_wx()
    frame = wx.Frame(None, size=(800, 500))
    try:
        figure = Figure(figsize=(8.0, 4.5), dpi=100)
        panel = support._create_time_series_panel(
            frame,
            figure,
            name="Shared time-series test panel",
        )

        assert panel.GetName() == "Shared time-series test panel"
        assert support._time_series_panel is panel
        assert support._time_series_plot_panel is not None
        assert support._time_series_canvas is not None
        assert support._time_series_figure is figure
        assert (
            support._time_series_plot_panel.minimum_canvas_size
            == GRAPH_PANEL_MIN_SIZE
        )

        floating = support._create_time_series_floating_panel(
            panel,
            name="Shared time-series controls",
        )
        status = support._create_time_series_status_label(
            panel,
            name="Shared time-series status",
            initial_text="Ready",
        )
        assert floating.GetName() == "Shared time-series controls"
        assert status.GetName() == "Shared time-series status"
        assert status.GetLabel() == "Ready"

        status_panel, status_label = (
            support._create_time_series_status_panel(
                panel,
                name="Shared live status",
                initial_text="Playback: 100 s",
            )
        )
        assert status_panel.GetName() == "Shared live status"
        assert status_label.GetName() == "Shared live status text"
        assert status_label.GetLabel() == "Playback: 100 s"
        frame.Show()
        wx_app.Yield()
        assert status_panel.IsExpanded()
        support._set_time_series_status("Playback: 120 s")
        assert support._time_series_status_label is status_label
        assert status_label.GetLabel() == "Playback: 120 s"
    finally:
        support._close_time_series_wx()
        frame.Destroy()


def test_time_series_wx_support_is_exported_from_both_paths() -> None:
    assert TimeSeriesWxPanelMixin is DirectTimeSeriesWxPanelMixin
