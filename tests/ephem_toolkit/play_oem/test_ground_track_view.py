"""Projection and wx-hosted Ground Track rendering checks."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from typing import Any, cast

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_track import GroundTrackCoordinates
from ephem_toolkit.play_oem.views import ground_track


@pytest.fixture(scope="module")
def wx_app() -> Iterator[Any]:
    import wx

    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available X display")
    app = wx.App.Get() or wx.App(False)
    yield app
    # Collect Matplotlib callback cycles while the native application still lives.
    gc.collect()


@pytest.mark.parametrize("name", ground_track.PROJECTION_NAMES)
@pytest.mark.parametrize("center", [-179.0, 0.0, 123.0])
def test_projection_covers_poles_and_center_seam(name: str, center: float) -> None:
    projection = ground_track._make_projection(name, center)
    x, y = projection(
        np.array([center, center, center - 180, center + 180]),
        np.array([-90, 90, 0, 0]),
        errcheck=True,
    )
    assert np.isfinite(x).all()
    assert np.isfinite(y).all()


@pytest.mark.parametrize("name", ground_track.PROJECTION_NAMES)
@pytest.mark.parametrize("background_style", ground_track.BACKGROUND_CHOICES)
def test_pan_rotates_map_without_horizontal_viewport_drift(
    name: str, background_style: str
) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    view = ground_track.GroundTrackView(
        cast(Any, None), None, None, cast(Any, None), "Test object"
    )
    view.projection_name = name
    view.background_style = background_style
    view._figure = Figure()
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)
    view._draw_map()
    canvas.draw()
    background = np.asarray(view._axes.images[0].get_array())
    assert np.isfinite(background).all()
    assert 0.0 <= float(background.min())
    assert float(background.max()) <= 1.0
    original_xlim = view._axes.get_xlim()
    original_ylim = view._axes.get_ylim()
    centers = []
    for _ in range(3):
        view._pan_map(20, 40)
        canvas.draw()
        centers.append(view.center_longitude_deg)
        assert view._axes.get_xlim() == pytest.approx(original_xlim)
        assert view._axes.get_ylim() == pytest.approx(original_ylim)
        x, _ = view._projection(view.center_longitude_deg, 0, errcheck=True)
        assert x == pytest.approx(0, abs=1e-6)
    assert centers[2] < centers[1] < centers[0] < 0
    # Zooming in permits vertical movement, bounded by the projected poles.
    zoomed_ylim = tuple(value * 0.5 for value in original_ylim)
    view._axes.set_ylim(zoomed_ylim)
    view._pan_map(0, 10)
    assert view._axes.get_ylim()[0] < zoomed_ylim[0]
    view._pan_map(0, 10000)
    assert view._axes.get_ylim()[0] == pytest.approx(original_ylim[0])
    view._pan_map(0, -10000)
    assert view._axes.get_ylim()[1] == pytest.approx(original_ylim[1])


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_wx_view_builds_controls_and_updates_minimum_elevation(wx_app: Any) -> None:
    import wx

    frame = wx.Frame(None)
    coordinates = GroundTrackCoordinates(
        np.array([0.0, 10.0]),
        np.deg2rad(np.array([0.0, 10.0])),
        np.deg2rad(np.array([0.0, 20.0])),
        np.array([0, 0]),
        "ITRF",
    )
    updates: list[int] = []
    view = ground_track.GroundTrackView(
        frame,
        None,
        coordinates,
        cast(Any, None),
        "Test object",
        on_minimum_elevation=updates.append,
    )
    content = view.build(cast(Any, None), cast(Any, None))
    assert isinstance(content, wx.Window)
    assert view._axes is not None
    assert "Ground Track" in view._axes.get_title()
    view._on_projection_choice(
        cast(Any, type("Event", (), {"GetString": lambda _self: "Equirectangular"})())
    )
    assert view.projection_name == "Equirectangular"
    view.set_minimum_elevation(15)
    assert view.minimum_elevation_deg == 15
    minimum_control = view._minimum_control
    assert minimum_control is not None
    assert minimum_control.GetValue() == 15
    view.close()
    frame.Destroy()
    wx_app.ProcessPendingEvents()


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_resizing_host_preserves_spin_control_sizes(wx_app: Any) -> None:
    import wx

    from ephem_toolkit.play_oem.graph_panel import GraphPanelHost

    frame = wx.Frame(None, size=(1500, 600))
    host = GraphPanelHost(frame, "Ground Track", lambda: None)
    coordinates = GroundTrackCoordinates(
        np.array([0.0, 10.0]),
        np.array([0.0, 0.1]),
        np.array([0.0, 0.2]),
        np.array([0, 0]),
        "ITRF",
    )
    view = ground_track.GroundTrackView(
        host.graph_scroller, None, coordinates, cast(Any, None), "Test object"
    )
    try:
        content = view.build(cast(Any, None), cast(Any, None))
        host.set_native_content(content)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(host, 1, wx.EXPAND)
        frame.SetSizer(sizer)
        frame.Show()
        original_map_width = None
        for width in (1500, 900, 640, 400, 1500):
            frame.SetSize((width, 600))
            wx_app.Yield()
            if "gtk3" in wx.PlatformInfo:
                for child in content.GetChildren():
                    if isinstance(
                        child,
                        (
                            wx.Choice,
                            wx.SpinCtrl,
                            wx.SpinCtrlDouble,
                            wx.Button,
                            wx.ToggleButton,
                        ),
                    ):
                        assert child.GetSize().height <= child.FromDIP(24)
            for control in (view._center_control, view._minimum_control):
                assert control is not None
                assert control.GetSize().width >= control.GetBestSize().width
                assert control.GetSize().height >= control.GetBestSize().height
            if width == 400:
                assert (
                    host.graph_scroller.GetVirtualSize().width
                    > host.graph_scroller.GetClientSize().width
                )
            assert view._canvas is not None
            view._canvas.draw()
            bounds = view._axes.get_window_extent()
            if original_map_width is None:
                original_map_width = bounds.width
            # GTK can redistribute a few pixels when a scrollbar appears.
            assert bounds.width >= original_map_width * 0.99
            if width <= 640:
                assert bounds.x0 <= 90
                assert view._canvas.GetSize().width - bounds.x1 <= 40
    finally:
        view.close()
        frame.Destroy()
        wx_app.Yield()
