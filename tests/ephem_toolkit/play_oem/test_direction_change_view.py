"""Tests for the direction-change playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.direction_change import DirectionChangeView
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
)


def test_direction_change_view_matches_plot_oem_series_and_updates_cursors() -> None:
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
    view = DirectionChangeView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.MINUTES)
        FigureCanvasAgg(figure).draw()

        assert [axes.get_ylabel() for axes in figure.axes] == [
            "Euler Angle (deg)",
            "Euler Angle Rate (deg/s)",
        ]
        assert [axes.get_title() for axes in figure.axes] == [
            "Euler-Angle Direction Change vs Time",
            "Euler-Angle Rate vs Time",
        ]
        assert all(
            axes.get_xlabel() == "Time from Start (minutes)" for axes in figure.axes
        )
        np.testing.assert_allclose(
            orbit_series.euler_angles_deg, plot_series.euler_angles_deg
        )
        np.testing.assert_allclose(
            orbit_series.euler_angle_rates_deg_s,
            plot_series.euler_angle_rates_deg_s,
        )
        for axes, values, suffix in (
            (figure.axes[0], plot_series.euler_angles_deg, ""),
            (figure.axes[1], plot_series.euler_angle_rates_deg_s, " rate"),
        ):
            for component, label in enumerate(("roll", "pitch", "yaw")):
                line = axes.lines[component]
                assert line.get_label() == f"ISS {label}{suffix}"
                np.testing.assert_allclose(line.get_xdata(), plot_series.elapsed_time)
                np.testing.assert_allclose(line.get_ydata(), values[:, component])

        view.update(160.0)
        for axes in figure.axes:
            np.testing.assert_allclose(axes.lines[-1].get_xdata(), [1.0, 1.0])
    finally:
        view.close()


def test_direction_change_view_handles_a_single_state() -> None:
    timestamps_s = [100.0]
    states_m = [np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    view = DirectionChangeView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.HOURS)
        assert all(
            axes.texts[0].get_text() == "Not enough samples" for axes in figure.axes
        )
        assert all(len(axes.lines) == 1 for axes in figure.axes)
    finally:
        view.close()
