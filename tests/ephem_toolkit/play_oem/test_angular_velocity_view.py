"""Tests for the angular-velocity playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.angular_velocity import AngularVelocityView
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
)


def test_angular_velocity_view_matches_plot_oem_series_and_updates_cursors() -> None:
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
    view = AngularVelocityView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.MINUTES)
        FigureCanvasAgg(figure).draw()

        assert [axes.get_ylabel() for axes in figure.axes] == [
            "Angular Velocity (deg/s)",
            "Angular Velocity (rad/s)",
        ]
        assert [axes.get_title() for axes in figure.axes] == [
            "Angular Velocity / Attitude Rate vs Time",
            "Angular Velocity / Attitude Rate (rad/s)",
        ]
        assert all(
            axes.get_xlabel() == "Time from Start (minutes)" for axes in figure.axes
        )
        np.testing.assert_allclose(
            orbit_series.angular_velocity_deg_s,
            plot_series.angular_velocity_deg_s,
        )
        np.testing.assert_allclose(
            orbit_series.angular_velocity_rad_s,
            plot_series.angular_velocity_rad_s,
        )
        for axes, values in zip(
            figure.axes,
            (
                plot_series.angular_velocity_deg_s,
                plot_series.angular_velocity_rad_s,
            ),
        ):
            line = axes.lines[0]
            valid_mask = values != 0.0
            assert line.get_label() == "ISS angular rate"
            np.testing.assert_allclose(
                line.get_xdata(), plot_series.elapsed_time[valid_mask]
            )
            np.testing.assert_allclose(line.get_ydata(), values[valid_mask])

        view.update(160.0)
        for axes in figure.axes:
            np.testing.assert_allclose(axes.lines[-1].get_xdata(), [1.0, 1.0])
    finally:
        view.close()


def test_angular_velocity_view_handles_a_single_state() -> None:
    timestamps_s = [100.0]
    states_m = [np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])]
    orbit_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    view = AngularVelocityView(timestamps_s[0], "ISS")

    try:
        figure = view.build(orbit_series, TimeUnit.HOURS)
        assert all(
            axes.texts[0].get_text() == "Not enough samples" for axes in figure.axes
        )
        assert all(len(axes.lines) == 1 for axes in figure.axes)
    finally:
        view.close()
