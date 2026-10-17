"""Tests for the Matplotlib 3D trajectory playback view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.trajectory3d import Trajectory3DView


def make_orbit():
    times_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    return (
        compute_orbit_series(times_s, states_m, TimeUnit.MINUTES),
        OemCursor(times_s, states_m),
    )


def test_trajectory_view_builds_contextual_3d_orbit_and_updates_marker() -> None:
    series, cursor = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")

    figure = view.build(series, TimeUnit.MINUTES)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()

    assert len(figure.axes) == 1
    axes = figure.axes[0]
    assert axes.name == "3d"
    assert axes.get_xlabel() == "X (km)"
    assert axes.get_ylabel() == "Y (km)"
    assert axes.get_zlabel() == "Z (km)"
    assert figure._suptitle is not None
    assert figure._suptitle.get_text() == "ISS | EME2000 / Earth"
    np.testing.assert_array_equal(
        axes.lines[0].get_data_3d()[0], series.position_km[:, 0]
    )

    state = cursor.lookup(160.0)
    view.update_cursor(state)
    assert view._cursor_artist is not None
    assert view._cursor_artist.get_visible()
    assert view._cursor_position_km == tuple(state.r_km)

    view.update_cursor(cursor.lookup(99.0))
    assert not view._cursor_artist.get_visible()
    assert view._cursor_position_km is None
    view.close()
    assert not figure.axes
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)
