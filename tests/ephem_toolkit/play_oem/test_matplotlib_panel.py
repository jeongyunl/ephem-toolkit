"""Tests for the Play-OEM wx Matplotlib panel."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import wx
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.widgets.matplotlib_panel import (
    MatplotlibPanel,
    _fit_canvas_bounds,
    _minimum_canvas_size,
)


@pytest.fixture
def wx_app() -> Iterator[Any]:
    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx display is not available")
    app = wx.App.Get() or wx.App(False)
    yield app


@pytest.mark.parametrize(
    ("figsize", "dpi_scale_factor", "expected_minimum"),
    [
        ((8.0, 4.5), 1.0, (480, 270)),
        ((5.0, 4.5), 1.0, (320, 288)),
        ((8.0, 6.0), 2.0, (320, 240)),
    ],
)
def test_minimum_canvas_size_preserves_figure_aspect_and_floors(
    figsize: tuple[float, float],
    dpi_scale_factor: float,
    expected_minimum: tuple[int, int],
) -> None:
    figure = Figure(figsize=figsize, dpi=100)

    minimum = _minimum_canvas_size(
        figure,
        dpi_scale_factor,
        preserve_aspect_ratio=True,
    )

    assert minimum == expected_minimum
    assert minimum[0] / minimum[1] == pytest.approx(figsize[0] / figsize[1], abs=0.01)
    assert minimum[0] >= 320
    assert minimum[1] >= 240


@pytest.mark.parametrize(
    ("dpi_scale_factor", "expected_minimum"),
    [(1.0, (320, 270)), (2.0, (320, 240))],
)
def test_flexible_canvas_minimum_keeps_height_floor_without_pairing_width(
    dpi_scale_factor: float,
    expected_minimum: tuple[int, int],
) -> None:
    figure = Figure(figsize=(8.0, 4.5), dpi=100)

    minimum = _minimum_canvas_size(
    figure,
    dpi_scale_factor,
    preserve_aspect_ratio=False,
    )

    assert minimum == expected_minimum


def test_fit_canvas_bounds_centers_and_preserves_aspect() -> None:
    bounds = _fit_canvas_bounds(
        host_width=1000,
        host_height=500,
        figure_aspect=16 / 9,
        toolbar_height=40,
        inset=8,
    )

    assert bounds is not None
    x, y, width, height = bounds
    assert width / height == pytest.approx(16 / 9, abs=0.01)
    assert x > 8
    assert y >= 48
    assert x + width <= 992
    assert y + height <= 492


def test_fit_canvas_bounds_fills_available_area_without_aspect_constraint() -> None:
    bounds = _fit_canvas_bounds(
        host_width=1000,
        host_height=500,
        figure_aspect=None,
        toolbar_height=40,
        inset=8,
    )

    assert bounds == (8, 48, 984, 444)


def test_fit_canvas_bounds_ignores_nonpositive_host_area() -> None:
    assert _fit_canvas_bounds(0, 700, 16 / 9, 40, 8) is None
    assert _fit_canvas_bounds(100, 40, 16 / 9, 40, 8) is None


def test_panel_owns_canvas_and_optional_toolbar(wx_app: Any) -> None:
    frame = wx.Frame(None)
    figure = Figure(figsize=(4.0, 3.0), dpi=100)

    without_toolbar = MatplotlibPanel(frame, figure)
    with_toolbar = MatplotlibPanel(
        frame,
        Figure(figsize=(4.0, 3.0), dpi=100),
        toolbar_factory=NavigationToolbar2WxAgg,
    )

    assert without_toolbar.figure is figure
    assert without_toolbar.canvas.figure is figure
    assert without_toolbar.toolbar is None
    assert with_toolbar.toolbar is not None
    assert with_toolbar.canvas.GetParent() is not None
    assert without_toolbar.GetMinSize().width >= 320
    frame.Destroy()


def test_panel_canvas_remains_aspect_fitted_when_resized(wx_app: Any) -> None:
    frame = wx.Frame(None, size=(1000, 700))
    panel = MatplotlibPanel(
        frame,
        Figure(figsize=(16.0, 9.0), dpi=100),
        preserve_aspect_ratio=True,
    )
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(sizer)
    frame.Show()

    for size in ((1000, 700), (800, 600)):
        frame.SetSize(size)
        frame.Layout()
        wx_app.Yield()
        panel._fit_canvas()
        canvas_size = panel.canvas.GetSize()
        host_size = panel._canvas_host.GetClientSize()

        assert canvas_size.width / canvas_size.height == pytest.approx(
            16 / 9, abs=0.01
        )
        assert canvas_size.width <= host_size.width
        assert canvas_size.height <= host_size.height

    frame.Destroy()


def test_panel_canvas_resizes_freely_and_keeps_minimum_height(wx_app: Any) -> None:
    frame = wx.Frame(None, size=(1000, 700))
    panel = MatplotlibPanel(
        frame,
        Figure(figsize=(16.0, 9.0), dpi=100),
        preserve_aspect_ratio=False,
    )
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(sizer)
    frame.Show()
    wx_app.Yield()

    panel._fit_canvas()
    host_size = panel._canvas_host.GetClientSize()
    canvas_size = panel.canvas.GetSize()

    assert panel.minimum_canvas_size == (320, 270)
    assert canvas_size.width == host_size.width - 16
    assert canvas_size.height == host_size.height - 16
    assert canvas_size.width / canvas_size.height != pytest.approx(16 / 9)

    frame.Destroy()
