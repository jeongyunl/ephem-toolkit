"""Range support tests for store-backed time-series views."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.data_view_base import StoreTimeSeriesView


def test_store_time_series_view_shares_axis_and_seek_conversion() -> None:
    view = StoreTimeSeriesView()
    view._initialize_store_time_series(100.0)
    figure = Figure()
    axes = figure.subplots()

    view._configure_time_series_axes(
        (axes,),
        start_time_s=100.0,
        time_unit=TimeUnit.MINUTES,
    )

    assert axes.get_xlabel() == "Time from Start (minutes)"
    assert getattr(axes, "_play_oem_seek_enabled") is True
    assert getattr(axes, "_play_oem_time_origin_s") == 100.0
    assert getattr(axes, "_play_oem_time_divisor_s") == 60.0
    assert view._axis_time(160.0) == 1.0
    np.testing.assert_array_equal(view._axis_times(np.array([160.0, 220.0])), [1.0, 2.0])
    assert view._absolute_time_from_axis(2.5) == 250.0
    assert view._axis_bounds(
        ResolvedTimeRange(130.0, 190.0),
        (100.0, 220.0),
    ) == (0.5, 1.5)

    view._close_store_time_series()


