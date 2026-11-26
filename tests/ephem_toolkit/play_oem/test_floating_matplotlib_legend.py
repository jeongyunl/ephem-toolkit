"""Tests for the floating Matplotlib legend widget."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import wx
from matplotlib.lines import Line2D

from ephem_toolkit.play_oem.widgets import FloatingMatplotlibLegend, PanelCorner


@pytest.fixture
def wx_app() -> Iterator[Any]:
    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx display is not available")
    app = wx.App.Get() or wx.App(False)
    yield app


def test_floating_matplotlib_legend_renders_and_sizes_to_entries(
    wx_app: Any,
) -> None:
    frame = wx.Frame(None, size=(640, 480))
    host = wx.Panel(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(host, 1, wx.EXPAND)
    legend_panel = FloatingMatplotlibLegend(
        host,
        name="Ground Track legend",
        corner=PanelCorner.BOTTOM_RIGHT,
    )
    handles = [
        Line2D([], [], label="Ground track"),
        Line2D([], [], label="0° horizon"),
    ]

    frame.Show()
    wx_app.Yield()
    legend_panel.set_handles(handles)
    legend_panel.canvas.draw()

    legends = legend_panel.figure.legends
    assert len(legends) == 1
    assert [text.get_text() for text in legends[0].get_texts()] == [
        "Ground track",
        "0° horizon",
    ]
    bounds = legends[0].get_window_extent(legend_panel.canvas.get_renderer())
    figure_width_px = (
        legend_panel.figure.get_figwidth() * legend_panel.figure.dpi
    )
    figure_height_px = (
        legend_panel.figure.get_figheight() * legend_panel.figure.dpi
    )
    assert 3 <= figure_width_px - bounds.width <= 5
    assert 3 <= figure_height_px - bounds.height <= 5

    scale = legend_panel.canvas.GetDPIScaleFactor()
    minimum_size = legend_panel.canvas.GetMinSize()
    assert minimum_size.width == pytest.approx(
        figure_width_px / scale,
        abs=1,
    )
    assert minimum_size.height == pytest.approx(
        figure_height_px / scale,
        abs=1,
    )
    assert legend_panel.GetName() == "Ground Track legend"
    handle_label = legend_panel.FindWindowByName(
        "Ground Track legend handle label"
    )
    assert handle_label is not None
    assert handle_label.GetLabel() == "≡"
    assert legend_panel.Close()
    frame.Destroy()
