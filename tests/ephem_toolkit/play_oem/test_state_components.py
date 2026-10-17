"""Tests for the Cartesian state-components playback view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.state_components import StateComponentsView


def make_series():
    return compute_orbit_series(
        [100.0, 160.0, 220.0],
        [
            np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
            np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
            np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
        ],
        TimeUnit.MINUTES,
    )


def test_state_components_view_builds_six_labeled_plots_and_synchronized_cursors():
    series = make_series()
    view = StateComponentsView(100.0, "GCRF / Earth")

    figure = view.build(series, TimeUnit.MINUTES)
    FigureCanvasAgg(figure).draw()

    assert len(figure.axes) == 6
    assert figure.axes[0].get_ylabel() == "X (km)"
    assert figure.axes[2].get_ylabel() == "Y (km)"
    assert figure.axes[4].get_ylabel() == "Z (km)"
    assert figure.axes[1].get_ylabel() == "VX (km/s)"
    assert figure.axes[3].get_ylabel() == "VY (km/s)"
    assert figure.axes[5].get_ylabel() == "VZ (km/s)"
    assert figure.axes[0].get_title() == "Position"
    assert figure.axes[1].get_title() == "Velocity"
    assert figure.axes[4].get_xlabel() == "Time from Start (minutes)"
    assert figure.axes[5].get_xlabel() == "Time from Start (minutes)"
    assert figure._suptitle is not None
    assert figure._suptitle.get_text() == "State Components | GCRF / Earth"

    np.testing.assert_array_equal(
        figure.axes[0].lines[0].get_ydata(), series.position_km[:, 0]
    )
    np.testing.assert_array_equal(
        figure.axes[1].lines[0].get_ydata(), series.velocity_km_s[:, 0]
    )
    for axes in figure.axes:
        np.testing.assert_array_equal(axes.lines[1].get_xdata(), [0.0, 0.0])

    view.update(160.0)
    for axes in figure.axes:
        np.testing.assert_array_equal(axes.lines[1].get_xdata(), [1.0, 1.0])

    view.close()
    assert not figure.axes
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)

