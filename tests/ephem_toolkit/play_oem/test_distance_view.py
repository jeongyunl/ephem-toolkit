"""Tests for the geocentric-distance playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.distance import GeocentricDistanceView
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
)


def test_distance_view_matches_plot_oem_series_and_updates_cursors() -> None:
    timestamps_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_100_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_200_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.MINUTES)
    plot_series = compute_plot_orbit_series(
        timestamps_s, states_m, PlotTimeUnit.MINUTES
    )
    view = GeocentricDistanceView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.MINUTES)
        FigureCanvasAgg(figure).draw()

        assert [axes.get_ylabel() for axes in figure.axes] == [
            "Geocentric Distance (km)",
            "Geocentric Distance Delta (km)",
        ]
        assert [axes.get_title() for axes in figure.axes] == [
            "Geocentric Distance vs Time",
            "Geocentric Distance Delta vs Time",
        ]
        assert figure.axes[-1].get_xlabel() == "Time from Start (minutes)"
        np.testing.assert_allclose(
            orbit_series.geocentric_distance_km, plot_series.geocentric_distance_km
        )
        np.testing.assert_allclose(
            figure.axes[0].lines[0].get_xdata(), plot_series.elapsed_time
        )
        np.testing.assert_allclose(
            figure.axes[0].lines[0].get_ydata(), plot_series.geocentric_distance_km
        )
        np.testing.assert_allclose(
            figure.axes[1].lines[0].get_xdata(), plot_series.elapsed_time[1:]
        )
        np.testing.assert_allclose(
            figure.axes[1].lines[0].get_ydata(),
            np.diff(plot_series.geocentric_distance_km),
        )

        view.update(160.0)
        for axes in figure.axes:
            np.testing.assert_allclose(axes.lines[-1].get_xdata(), [1.0, 1.0])
    finally:
        view.close()


def test_distance_view_shows_empty_delta_for_a_single_state() -> None:
    timestamps_s = [100.0]
    states_m = [np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    view = GeocentricDistanceView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.HOURS)
        assert figure.axes[1].texts[0].get_text() == "Not enough samples"
        assert len(figure.axes[0].lines) == 2
        assert len(figure.axes[1].lines) == 1
    finally:
        view.close()
