"""Projection and wx-hosted Ground Track rendering checks."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from typing import Any, cast

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import StoreViewContext
from ephem_toolkit.play_oem.views import ground_track
from ephem_toolkit.play_oem.views.plotting import MAX_DISPLAY_POINTS_PER_SEGMENT


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


@pytest.mark.parametrize("reverse", [False, True])
def test_scrollbar_mapping_round_trips_viewport_center(reverse: bool) -> None:
    low, high, world_half_extent = -90.0, 10.0, 100.0
    position, overflow = ground_track._scrollbar_metrics(
        low, high, world_half_extent, reverse=reverse
    )

    center = ground_track._scrollbar_center(
        position,
        high - low,
        world_half_extent,
        reverse=reverse,
    )

    assert 0 <= position <= ground_track._SCROLLBAR_TRAVEL
    assert center == pytest.approx(
        (low + high) * 0.5,
        abs=overflow / (2 * ground_track._SCROLLBAR_TRAVEL) + 1e-12,
    )
    first_center = ground_track._scrollbar_center(
        0, high - low, world_half_extent, reverse=reverse
    )
    last_center = ground_track._scrollbar_center(
        ground_track._SCROLLBAR_TRAVEL,
        high - low,
        world_half_extent,
        reverse=reverse,
    )
    if reverse:
        assert first_center > last_center
    else:
        assert first_center < last_center


def test_scrollbar_mapping_disables_full_world_and_clamps_positions() -> None:
    position, overflow = ground_track._scrollbar_metrics(-100.0, 100.0, 100.0)
    assert position == 0
    assert overflow == 0.0

    left_position, _ = ground_track._scrollbar_metrics(-200.0, -100.0, 100.0)
    right_position, _ = ground_track._scrollbar_metrics(100.0, 200.0, 100.0)
    assert left_position == 0
    assert right_position == ground_track._SCROLLBAR_TRAVEL


def test_ground_track_scrollbars_apply_shared_mapping_to_both_axes() -> None:
    from matplotlib.figure import Figure

    class ScrollBar:
        def __init__(self) -> None:
            self.values: tuple[int, int, int, int] | None = None
            self.enabled = False

        def SetScrollbar(
            self, position: int, thumb: int, range_: int, thumb_size: int
        ) -> None:
            self.values = (position, thumb, range_, thumb_size)

        def Enable(self, enabled: bool) -> None:
            self.enabled = enabled

    class ScrollEvent:
        def __init__(self, position: int) -> None:
            self.position = position

        def GetPosition(self) -> int:
            return self.position

    view = ground_track.GroundTrackView(cast(Any, None), "Test object")
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111)
    view._projection = ground_track._make_projection("Equirectangular", 0.0)
    view._horizontal_scroll = ScrollBar()
    view._vertical_scroll = ScrollBar()
    world_x = abs(float(view._projection(180.0, 0.0)[0]))
    world_y = abs(float(view._projection(0.0, 90.0)[1]))
    view._axes.set_xlim(-world_x * 0.5, world_x * 0.5)
    view._axes.set_ylim(-world_y * 0.5, world_y * 0.5)

    view._update_scrollbars()

    assert view._horizontal_scroll.values == (
        ground_track._SCROLLBAR_TRAVEL // 2,
        ground_track._SCROLLBAR_THUMB_SIZE,
        ground_track._SCROLLBAR_RANGE,
        ground_track._SCROLLBAR_THUMB_SIZE,
    )
    assert view._vertical_scroll.values == view._horizontal_scroll.values
    assert view._horizontal_scroll.enabled
    assert view._vertical_scroll.enabled

    view._on_horizontal_scroll(ScrollEvent(0))
    view._on_vertical_scroll(ScrollEvent(0))
    assert view._axes.get_xlim() == pytest.approx((-world_x, 0.0))
    assert view._axes.get_ylim() == pytest.approx((0.0, world_y))
    view._update_scrollbars()
    assert view._horizontal_scroll.values is not None
    assert view._horizontal_scroll.values[0] == 0
    assert view._vertical_scroll.values is not None
    assert view._vertical_scroll.values[0] == 0

    view._axes.set_xlim(-world_x, world_x)
    view._axes.set_ylim(-world_y, world_y)
    view._update_scrollbars()
    assert not view._horizontal_scroll.enabled
    assert not view._vertical_scroll.enabled
    view.close()


@pytest.mark.parametrize("name", ground_track.PROJECTION_NAMES)
@pytest.mark.parametrize("background_style", ground_track.BACKGROUND_CHOICES)
def test_pan_rotates_map_without_horizontal_viewport_drift(
    name: str, background_style: str
) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    view = ground_track.GroundTrackView(
        cast(Any, None), "Test object"
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


def test_ground_track_store_view_uses_bound_queries_and_point_footprints() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    timestamps_s = np.array([0.0, 10.0, 20.0, 30.0])
    states_m = np.array(
        [
            [7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0],
            [0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0],
            [-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0],
            [0.0, -7_000_000.0, 0.0, 7_500.0, 0.0, 0.0],
        ]
    )
    store = OemDataStore()
    epoch = store.begin(len(timestamps_s))
    reservation = store.reserve(len(timestamps_s))
    reservation.raw[:, 0] = timestamps_s
    reservation.raw[:, 1:7] = states_m
    reservation.segment_ids[:] = [0, 0, 1, 1]
    store.commit(reservation, len(timestamps_s))
    store.mark_complete(epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")))
    snapshot = store.snapshot()
    store.ground_track(snapshot, (0.0, 30.0), wait=True)
    store.ground_track(snapshot, (10.0, 20.0), wait=True)
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 30.0),
        coverage=(0.0, 30.0),
    )

    view = ground_track.GroundTrackView(
        cast(Any, None), "Test object"
    )
    view._store_binding.bind(context)
    view._store_context = context
    view._effective_plot_range = context.bounds_s
    view._figure = Figure()
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)
    view._draw_map()

    assert view._store_track_query is not None
    assert view._store_track_query.coverage.complete
    assert len(view._track_artists) == 2
    assert all(
        len(artist.get_xdata()) <= MAX_DISPLAY_POINTS_PER_SEGMENT
        for artist in view._track_artists
    )

    view.update(10.0)
    assert view._marker is not None and len(view._marker.get_xdata()) == 1
    assert view._last_footprints is not None

    view.set_time_range(ResolvedTimeRange(10.0, 20.0), context.coverage)
    assert view._store_track_query is not None
    assert len(view._track_artists) == 2
    view.set_time_range(None, context.coverage)
    assert view._store_track_query is not None
    assert view._store_track_query.coverage.requested_s is None
    assert not view._track_artists
    view.close()
    assert "ground-track" not in store._tier_interest
    assert "earth-fixed" not in store._tier_interest


def test_ground_track_axes_follow_canvas_height_without_fixed_aspect() -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    view = ground_track.GroundTrackView(
        cast(Any, None), "Test object"
    )
    view._figure = Figure(figsize=(8.0, 4.0), dpi=100)
    canvas = FigureCanvasAgg(view._figure)
    view._canvas = cast(Any, canvas)
    view._axes = view._figure.add_subplot(111)
    view._draw_map()

    canvas.draw()
    tall_axes_height = view._axes.get_window_extent().height
    view._figure.set_size_inches(8.0, 2.0)
    canvas.draw()

    assert view._axes.get_aspect() == "auto"
    assert view._axes.get_window_extent().height < tall_axes_height
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
    updates: list[int] = []
    view = ground_track.GroundTrackView(
        frame,
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
    view = ground_track.GroundTrackView(
        host.graph_scroller,
        "Test object",
    )
    try:
        content = view.build(cast(Any, None), cast(Any, None))
        host.set_native_content(content)
        assert content.GetMinSize().height == 64
        assert view._canvas is not None
        assert view._canvas.GetMinSize().height == 64
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
