"""Range-filtering and segmentation tests for time-series display artists."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.views.plotting import SegmentedPlotHistory


def test_history_filters_inclusively_and_preserves_segment_gaps() -> None:
    figure = Figure()
    axes = figure.subplots()
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
    segment_ids = np.array([0, 0, -1, 1, 1, 1])
    history = SegmentedPlotHistory(axes, x, y, segment_ids)

    assert history.update((1.0, 4.0))
    np.testing.assert_array_equal(history.artists[0].get_xdata(), [1.0])
    np.testing.assert_array_equal(history.artists[0].get_ydata(), [11.0])
    np.testing.assert_array_equal(history.artists[1].get_xdata(), [3.0, 4.0])
    assert history.artists[0].get_marker() == "."
    assert history.artists[1].get_marker() == "None"


def test_filtering_precedes_decimation_and_keeps_narrow_window_extrema() -> None:
    figure = Figure()
    axes = figure.subplots()
    x = np.arange(100_000, dtype=float)
    y = np.zeros_like(x)
    y[50_001] = 1234.0
    history = SegmentedPlotHistory(
        axes, x, y, np.zeros(len(x), dtype=int), max_display_points=20
    )

    assert history.update((50_000.0, 50_002.0))
    line = history.artists[0]
    np.testing.assert_array_equal(line.get_xdata(), [50_000, 50_001, 50_002])
    assert 1234.0 in line.get_ydata()


def test_empty_overlap_and_sample_free_intervals_have_distinct_states() -> None:
    figure = Figure()
    axes = figure.subplots()
    history = SegmentedPlotHistory(
        axes, np.array([0.0, 10.0]), np.array([1.0, 2.0]), np.array([0, 0])
    )

    assert not history.update(None, empty_range=True)
    assert history._empty_range_text.get_visible()
    assert not history._empty_text.get_visible()

    assert not history.update((4.0, 6.0))
    assert history._empty_text.get_visible()
    assert not history._empty_range_text.get_visible()


def test_time_range_support_axis_limits_do_not_change_y_scale() -> None:
    from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView

    # Exercise the public view contract using an actual series with fixed y data.
    from ephem_toolkit.play_oem.series import OrbitSeries
    from ephem_toolkit.play_oem.time_unit import TimeUnit

    values = np.array([1.0, 4.0, 2.0])
    orbit = OrbitSeries(
        elapsed_time=np.array([0.0, 1.0, 2.0]),
        position_km=np.ones((3, 3)),
        velocity_km_s=np.ones((3, 3)),
        velocity_magnitude_km_s=values,
        geocentric_distance_km=values + 1,
        altitude_km=values + 2,
        rtn_elapsed_time=np.array([1.0, 2.0]),
        rtn_delta_km=np.ones((2, 6)),
        direction_change_angle_deg=values,
        direction_change_rate_deg_s=values,
        angular_velocity_deg_s=values,
        angular_velocity_rad_s=values,
        euler_angles_deg=np.ones((3, 3)),
        euler_angle_rates_deg_s=np.ones((3, 3)),
        segment_ids=np.array([0, 0, 0]),
        rtn_segment_ids=np.array([0, 0]),
    )
    view = SpeedAltitudeView(100.0)
    figure = view.build(orbit, TimeUnit.MINUTES)
    try:
        full_y = figure.axes[0].get_ylim()
        view.set_time_range(ResolvedTimeRange(160.0, 160.0), (100.0, 220.0))
        assert figure.axes[0].get_xlim() == (0.5, 1.5)
        assert figure.axes[0].get_ylim() == full_y
        np.testing.assert_array_equal(figure.axes[0].lines[0].get_xdata(), [1.0])
        assert not view.cursor_artists[0].get_visible()
        figure.axes[0].set_xlim(-5.0, 5.0)
        assert figure.axes[0].get_xlim() == (0.5, 1.5)
        view.update(160.0)
        assert view.cursor_artists[0].get_visible()
        view.set_time_range(ResolvedTimeRange(100.0, 220.0), (100.0, 220.0))
        assert figure.axes[0].get_xlim() == (0.0, 2.0)
        assert view.cursor_artists[0].get_visible()
        figure.axes[0].set_xlim(0.25, 0.75)
        assert figure.axes[0].get_xlim() == (0.25, 0.75)
    finally:
        view.close()


def test_speed_altitude_data_update_preserves_figure_and_line_artists() -> None:
    from dataclasses import replace

    from ephem_toolkit.play_oem.series import OrbitSeries
    from ephem_toolkit.play_oem.time_unit import TimeUnit
    from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView

    values = np.array([1.0, 4.0, 2.0])
    orbit = OrbitSeries(
        elapsed_time=np.array([0.0, 1.0, 2.0]),
        position_km=np.ones((3, 3)),
        velocity_km_s=np.ones((3, 3)),
        velocity_magnitude_km_s=values,
        geocentric_distance_km=values + 1,
        altitude_km=values + 2,
        rtn_elapsed_time=np.array([1.0, 2.0]),
        rtn_delta_km=np.ones((2, 6)),
        direction_change_angle_deg=values,
        direction_change_rate_deg_s=values,
        angular_velocity_deg_s=values,
        angular_velocity_rad_s=values,
        euler_angles_deg=np.ones((3, 3)),
        euler_angle_rates_deg_s=np.ones((3, 3)),
        segment_ids=np.array([0, 0, 0]),
        rtn_segment_ids=np.array([0, 0]),
    )
    view = SpeedAltitudeView(100.0)
    figure = view.build(orbit, TimeUnit.MINUTES)
    lines = tuple(view._histories[0].artists)
    figure.axes[0].set_ylim(0.0, 5.0)
    updated = replace(
        orbit,
        elapsed_time=np.array([0.0, 1.0, 2.0, 3.0]),
        velocity_magnitude_km_s=np.array([2.0, 3.0, 4.0, 5.0]),
        altitude_km=np.array([10.0, 20.0, 30.0, 40.0]),
        segment_ids=np.array([0, 0, 0, 0]),
    )

    try:
        assert view.update_data(updated, TimeUnit.MINUTES)
        view.set_time_range(ResolvedTimeRange(100.0, 160.0), (100.0, 280.0))

        assert view._figure is figure
        assert view._histories[0].artists[0] is lines[0]
        assert len(view._histories[0].artists) == 1
        np.testing.assert_array_equal(lines[0].get_xdata(), [0.0, 1.0])
        assert figure.axes[0].get_ylim() == (0.0, 5.0)
        assert figure.axes[1].get_ylim()[1] > 40.0
        changed_structure = replace(
            updated, segment_ids=np.array([0, 0, 1, 1])
        )
        assert not view.update_data(changed_structure, TimeUnit.MINUTES)
    finally:
        view.close()


def test_time_series_views_accept_appended_data_in_place() -> None:
    from ephem_toolkit.play_oem.series import compute_orbit_series
    from ephem_toolkit.play_oem.time_unit import TimeUnit
    from ephem_toolkit.play_oem.views.angular_velocity import AngularVelocityView
    from ephem_toolkit.play_oem.views.direction_change import DirectionChangeView
    from ephem_toolkit.play_oem.views.distance import GeocentricDistanceView
    from ephem_toolkit.play_oem.views.rtn import RtnDeltaView
    from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView
    from ephem_toolkit.play_oem.views.state_components import StateComponentsView

    states = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
        np.array([0.0, -7_000_000.0, 0.0, 7_500.0, 0.0, 0.0]),
    ]
    initial = compute_orbit_series(
        [100.0, 160.0, 220.0], states[:3], TimeUnit.MINUTES
    )
    updated = compute_orbit_series(
        [100.0, 160.0, 220.0, 280.0], states, TimeUnit.MINUTES
    )
    views = (
        SpeedAltitudeView(100.0),
        AngularVelocityView(100.0, "ISS"),
        DirectionChangeView(100.0, "ISS"),
        GeocentricDistanceView(100.0, "ISS"),
        RtnDeltaView(100.0, "ISS"),
        StateComponentsView(100.0, "GCRF / Earth"),
    )

    for view in views:
        figure = view.build(initial, TimeUnit.MINUTES)
        try:
            assert view.update_data(updated, TimeUnit.MINUTES)
            assert figure.axes
        finally:
            view.close()
