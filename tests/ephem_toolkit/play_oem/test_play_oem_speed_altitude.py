"""Tests for the static speed and altitude plot view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView


def test_speed_altitude_view_builds_labeled_static_series_and_cursor() -> None:
    series = compute_orbit_series(
        [100.0, 160.0, 220.0],
        [
            np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
            np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
            np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
        ],
        TimeUnit.MINUTES,
    )
    view = SpeedAltitudeView(t_start_s=100.0)

    figure = view.build(series, TimeUnit.MINUTES)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()

    assert len(figure.axes) == 2
    assert figure.axes[0].get_ylabel() == "Speed (km/s)"
    assert figure.axes[1].get_ylabel() == "Altitude (km)"
    assert figure.axes[1].get_xlabel() == "Time from Start (minutes)"
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [0.0, 0.0])

    view.update(160.0)
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [1.0, 1.0])

    view.close()
    assert not figure.axes
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)
