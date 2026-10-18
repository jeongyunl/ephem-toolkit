"""Parity tests for play-oem OEM loading, filtering and derived series."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from ephem_toolkit.play_oem.data import filter_states_by_duration, read_oem_states
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit as PlotTimeUnit,
    compute_orbit_series as compute_plot_orbit_series,
    filter_states_by_duration as filter_plot_states_by_duration,
    read_oem_states as read_plot_oem_states,
)


@pytest.fixture
def iss_oem_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"


def test_read_oem_states_matches_plot_oem(iss_oem_path: Path) -> None:
    play_oem_data, play_timestamps, play_states = read_oem_states(iss_oem_path)
    plot_oem_data, plot_timestamps, plot_states = read_plot_oem_states(iss_oem_path)

    assert len(play_oem_data.states) == len(plot_oem_data.states)
    np.testing.assert_array_equal(play_timestamps, plot_timestamps)
    np.testing.assert_allclose(play_states, plot_states)


def test_duration_filter_matches_plot_oem(iss_oem_path: Path) -> None:
    _, timestamps_s, states_m = read_oem_states(iss_oem_path)

    play_timestamps, play_states = filter_states_by_duration(
        timestamps_s, states_m, 3600.0
    )
    plot_timestamps, plot_states = filter_plot_states_by_duration(
        timestamps_s, states_m, 3600.0
    )

    np.testing.assert_array_equal(play_timestamps, plot_timestamps)
    np.testing.assert_allclose(play_states, plot_states)
    assert play_timestamps[-1] <= timestamps_s[0] + 3600.0


def test_compute_orbit_series_matches_plot_oem(iss_oem_path: Path) -> None:
    _, timestamps_s, states_m = read_oem_states(iss_oem_path)
    timestamps_s, states_m = filter_states_by_duration(timestamps_s, states_m, 3600.0)

    play_series = compute_orbit_series(timestamps_s, states_m, TimeUnit.HOURS)
    plot_series = compute_plot_orbit_series(timestamps_s, states_m, PlotTimeUnit.HOURS)

    for field in fields(play_series):
        if field.name in ("segment_ids", "rtn_segment_ids"):
            continue
        np.testing.assert_allclose(
            getattr(play_series, field.name),
            getattr(plot_series, field.name),
            err_msg=f"Mismatch in derived series field {field.name}",
        )


def test_oem_loader_preserves_multiple_segment_ids() -> None:
    from ephem_toolkit.core.ccsds.oem import CcsdsOem

    text = """CCSDS_OEM_VERS = 2.0
META_START
OBJECT_NAME = TEST
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:00:00 7000 0 0 0 7.5 0
2026-01-01T00:00:10 7000 1 0 0 7.5 0
META_START
OBJECT_NAME = TEST
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:10:00 7000 2 0 0 7.5 0
2026-01-01T00:10:10 7000 3 0 0 7.5 0
"""
    parsed = CcsdsOem.from_text(text)
    assert parsed.segment_ids == [0, 0, 1, 1]


def test_series_does_not_compute_cross_segment_deltas_or_rates() -> None:
    timestamps = [0.0, 10.0, 100.0, 110.0]
    states = [
        np.array([7_000_000.0, index * 1_000.0, 0.0, 0.0, 7_500.0, 0.0])
        for index in range(4)
    ]
    computed = compute_orbit_series(
        timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1]
    )

    assert computed.segment_ids.tolist() == [0, 0, 1, 1]
    assert computed.rtn_segment_ids.tolist() == [0, -1, 1]
    assert np.isnan(computed.rtn_delta_km[1]).all()
    assert computed.angular_velocity_deg_s[2] == 0.0
    assert np.all(computed.euler_angle_rates_deg_s[2] == 0.0)


def test_time_series_view_plots_oem_segments_as_separate_runs() -> None:
    from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView

    timestamps = [0.0, 10.0, 100.0, 110.0]
    states = [
        np.array([7_000_000.0, index * 1_000.0, 0.0, 0.0, 7_500.0, 0.0])
        for index in range(4)
    ]
    computed = compute_orbit_series(
        timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1]
    )
    view = SpeedAltitudeView(timestamps[0])
    figure = view.build(computed, TimeUnit.MINUTES)
    try:
        for axes in figure.axes:
            series_lines = [line for line in axes.lines if line.get_label() != "_child0"]
            assert len(series_lines) == 2
            assert [len(line.get_xdata()) for line in series_lines] == [2, 2]
    finally:
        view.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("m", TimeUnit.MINUTES),
        ("minutes", TimeUnit.MINUTES),
        ("H", TimeUnit.HOURS),
        ("hours", TimeUnit.HOURS),
    ],
)
def test_time_unit_parsing_matches_plot_oem(value: str, expected: TimeUnit) -> None:
    assert TimeUnit.from_string(value) is expected
    assert TimeUnit.from_string(value).value == PlotTimeUnit.from_string(value).value
