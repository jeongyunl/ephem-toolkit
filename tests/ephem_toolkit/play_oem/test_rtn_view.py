"""Tests for the RTN position-delta playback view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.rtn import RtnDeltaView
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
)


def test_rtn_view_matches_plot_oem_series_and_updates_all_cursors() -> None:
    timestamps_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.MINUTES)
    plot_series = compute_plot_orbit_series(
        timestamps_s, states_m, PlotTimeUnit.MINUTES
    )
    view = RtnDeltaView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.MINUTES)
        FigureCanvasAgg(figure).draw()

        assert len(figure.axes) == 3
        assert [axes.get_title() for axes in figure.axes] == [
            "Radial Position Delta vs Time",
            "Transverse Position Delta vs Time",
            "Normal Position Delta vs Time",
        ]
        assert [axes.get_ylabel() for axes in figure.axes] == [
            "Radial Delta (km)",
            "Transverse Delta (km)",
            "Normal Delta (km)",
        ]
        assert figure.axes[-1].get_xlabel() == "Time from Start (minutes)"
        np.testing.assert_allclose(
            orbit_series.rtn_elapsed_time, plot_series.rtn_elapsed_time
        )
        np.testing.assert_allclose(orbit_series.rtn_delta_km, plot_series.rtn_delta_km)
        for component, axes in enumerate(figure.axes):
            line = axes.lines[0]
            assert line.get_label() == "ISS"
            np.testing.assert_allclose(line.get_xdata(), plot_series.rtn_elapsed_time)
            np.testing.assert_allclose(
                line.get_ydata(), plot_series.rtn_delta_km[:, component]
            )

        view.update(160.0)
        for axes in figure.axes:
            np.testing.assert_allclose(axes.lines[-1].get_xdata(), [1.0, 1.0])
    finally:
        view.close()


def test_rtn_view_shows_not_enough_samples_for_one_state() -> None:
    timestamps_s = [100.0]
    states_m = [np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    view = RtnDeltaView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.HOURS)
        assert figure.axes[0].texts[0].get_text() == "Not enough samples"
        assert all(len(axes.lines) == 1 for axes in figure.axes)
    finally:
        view.close()


def test_rtn_view_rejects_mismatched_delta_arrays() -> None:
    timestamps_s = [100.0, 160.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
    ]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.MINUTES)
    orbit_series.rtn_elapsed_time = np.array([])
    view = RtnDeltaView(timestamps_s[0], "ISS")

    with pytest.raises(ValueError, match="RTN delta arrays"):
        view.build(orbit_series, TimeUnit.MINUTES)
