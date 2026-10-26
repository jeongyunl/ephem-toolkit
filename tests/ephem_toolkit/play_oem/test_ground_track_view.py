"""Projection and wx-hosted Ground Track rendering checks."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from typing import Any, cast

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_track import GroundTrackCoordinates
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
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
    np.testing.assert_allclose(
        view._axes.get_xticks(),
        view._projection(np.arange(-180.0, 181.0, 60.0), np.zeros(7))[0],
        atol=1e-5,
    )
    original_zero_x = view._axes.get_xticks()[3]
    centers = []
    for _ in range(3):
        view._pan_map(20, 40)
        canvas.draw()
        centers.append(view.center_longitude_deg)
        assert view._axes.get_xlim() == pytest.approx(original_xlim)
        assert view._axes.get_ylim() == pytest.approx(original_ylim)
        x, _ = view._projection(view.center_longitude_deg, 0, errcheck=True)
        assert x == pytest.approx(0, abs=1e-6)
        tick_longitudes, _ = view._projection(
            view._axes.get_xticks(),
            np.zeros_like(view._axes.get_xticks()),
            inverse=True,
        )
        np.testing.assert_allclose(np.diff(tick_longitudes), 60.0, atol=1e-5)
        np.testing.assert_allclose(
            tick_longitudes / 60.0, np.round(tick_longitudes / 60.0), atol=1e-5
        )
        zero_index = int(np.argmin(np.abs(tick_longitudes)))
        assert view._axes.get_xticks()[zero_index] > original_zero_x
        assert view._axes.get_xticklabels()[zero_index].get_text() == "0°"
        meridian = view._axes.lines[zero_index]
        np.testing.assert_allclose(
            meridian.get_xdata(),
            view._projection(
                np.zeros(181), np.linspace(-90.0, 90.0, 181), errcheck=True
            )[0],
            atol=1e-5,
        )
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


def test_ground_track_filters_cached_coordinates_before_seam_splitting() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    coordinates = GroundTrackCoordinates(
        np.arange(5, dtype=float),
        np.zeros(5),
        np.deg2rad(np.array([-10.0, 170.0, 179.0, -179.0, -170.0])),
        np.zeros(5, dtype=int),
        "ITRF",
    )
    view = ground_track.GroundTrackView(
        cast(Any, None),
        None,
        coordinates,
        cast(Any, type("CursorBounds", (), {"t_start": 0.0, "t_end": 4.0})()),
        "Test object",
    )
    view._figure = Figure()
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)
    view._draw_map()
    before = (view._axes.get_xlim(), view._axes.get_ylim())

    view.set_time_range(ResolvedTimeRange(1.0, 3.0), (0.0, 4.0))

    assert len(view._track_artists) == 2
    assert (view._axes.get_xlim(), view._axes.get_ylim()) == before
    projected_east = view._projection(np.array([170.0, 179.0, 180.0]), np.zeros(3))[0]
    projected_west = view._projection(np.array([-180.0, -179.0]), np.zeros(2))[0]
    np.testing.assert_allclose(view._track_artists[0].get_xdata(), projected_east)
    np.testing.assert_allclose(view._track_artists[1].get_xdata(), projected_west)

    view.set_time_range(None, (0.0, 4.0))
    assert not view._track_artists
    assert view._track_status_artist.get_visible()
    assert view._track_status_artist.get_text() == (
        "Plot range does not overlap OEM coverage"
    )

    view.set_time_range(ResolvedTimeRange(1.1, 1.9), (0.0, 4.0))
    assert not view._track_artists
    assert view._track_status_artist.get_text() == "No ground track samples in plot range"
    view.close()


@pytest.mark.parametrize(
    ("projection_name", "center_longitude_deg"),
    [
        ("Equirectangular", -179.0),
        ("Equirectangular", 0.0),
        ("Robinson", 123.0),
    ],
)
def test_station_markers_follow_projection_and_center_longitude(
    projection_name: str, center_longitude_deg: float
) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    station = GroundStation("seam-site", "Seam Site", 12.0, 179.5, 100.0, 15)
    view = ground_track.GroundTrackView(
        cast(Any, None),
        None,
        None,
        cast(Any, None),
        "Test object",
        stations=[station],
    )
    view.projection_name = projection_name
    view.center_longitude_deg = center_longitude_deg
    view._figure = Figure()
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)

    view._draw_map()

    relative_longitude = ground_track._normalized_longitude(
        station.longitude_deg - center_longitude_deg
    )
    expected_x, expected_y = view._projection(
        relative_longitude + center_longitude_deg,
        station.latitude_deg,
        errcheck=True,
    )
    marker = view._station_artists[station.station_id]
    assert marker.get_xdata()[0] == pytest.approx(expected_x)
    assert marker.get_ydata()[0] == pytest.approx(expected_y)
    assert len(view._station_label_artists) == 1
    view.close()


def test_station_marker_selection_opens_passes_without_seeking() -> None:
    from matplotlib.backend_bases import MouseEvent
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    station = GroundStation("site-id", "Site", 0.0, 0.0, 0.0, 10)
    lookup_calls: list[float] = []
    cursor = type(
        "Cursor",
        (),
        {
            "t_start": 0.0,
            "t_end": 10.0,
            "lookup": lambda _self, time_s: lookup_calls.append(time_s),
        },
    )()
    opened: list[str] = []
    view = ground_track.GroundTrackView(
        cast(Any, None),
        None,
        None,
        cast(Any, cursor),
        "Test object",
        stations=[station],
        on_open_passes=opened.append,
    )
    view._figure = Figure()
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)
    view._draw_map()
    canvas.draw()

    marker_x, marker_y = view._station_artists[station.station_id].get_data()
    pixel_x, pixel_y = view._axes.transData.transform((marker_x[0], marker_y[0]))
    press = MouseEvent("button_press_event", canvas, pixel_x, pixel_y, button=1)
    release = MouseEvent("button_release_event", canvas, pixel_x, pixel_y, button=1)
    view._on_map_press(press)
    view._on_map_release(release)
    view._open_selected_station_passes()

    assert view._selected_station_id == station.station_id
    assert opened == [station.station_id]
    assert lookup_calls == []
    view.close()


def test_station_updates_retain_viewport_and_remove_stale_markers() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    first = GroundStation("first", "First", 0.0, 0.0, 0.0)
    replacement = GroundStation("replacement", "Replacement", 20.0, 30.0, 0.0)
    view = ground_track.GroundTrackView(
        cast(Any, None),
        None,
        None,
        cast(Any, None),
        "Test object",
        stations=[first],
    )
    view._figure = Figure()
    view._canvas = cast(Any, FigureCanvasAgg(view._figure))
    view._axes = view._figure.add_subplot(111)
    view._draw_map()
    view._select_station(first.station_id)
    view._axes.set_xlim(-1_000_000.0, 1_000_000.0)
    expected_xlim = view._axes.get_xlim()

    view.set_stations([replacement])

    assert view._selected_station_id is None
    assert set(view._station_artists) == {replacement.station_id}
    assert view._axes.get_xlim() == expected_xlim
    view.set_stations([])
    assert not view._station_artists
    view.close()


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
        cast(Any, type("CursorBounds", (), {"t_start": 0.0, "t_end": 10.0})()),
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
    view._on_minimum_control(
        cast(Any, type("Event", (), {"GetInt": lambda _self: 15})())
    )
    assert view.minimum_elevation_deg == 15
    assert updates == [15]
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
        host.graph_scroller,
        None,
        coordinates,
        cast(Any, type("CursorBounds", (), {"t_start": 0.0, "t_end": 10.0})()),
        "Test object",
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
            if width <= 640 and "gtk3" in wx.PlatformInfo:
                assert bounds.x0 <= content.FromDIP(90)
                assert view._canvas.GetSize().width - bounds.x1 <= 40
    finally:
        view.close()
        frame.Destroy()
        wx_app.Yield()
