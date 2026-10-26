"""Parity tests for play-oem OEM loading, filtering and derived series."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.time_utils import datetime_to_tt_s, iso8601_to_datetime
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.data import filter_states_by_duration, read_oem_states
from ephem_toolkit.play_oem.playback_data import load_playback_data
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


def test_loaded_playback_exposes_oem_metadata_slider_bounds(
    iss_oem_path: Path,
) -> None:
    loaded = load_playback_data(iss_oem_path)
    metadata = CcsdsOem.from_file(iss_oem_path).meta
    expected = (
        datetime_to_tt_s(iso8601_to_datetime(metadata.start_time)),
        datetime_to_tt_s(iso8601_to_datetime(metadata.stop_time)),
    )

    assert loaded.slider_bounds == expected


def test_playback_data_exposes_ground_track_source_metadata(iss_oem_path: Path) -> None:
    loaded = load_playback_data(iss_oem_path)

    assert loaded.ground_track_source is not None
    assert loaded.ground_track_source.center_name.strip().upper() == "EARTH"
    assert loaded.ground_track_source.frame_name == "EME2000"
    assert (
        loaded.ground_track_source.timestamps_s.shape == loaded.series.segment_ids.shape
    )
    assert loaded.ground_track_source.states_m.shape == (
        len(loaded.series.segment_ids),
        6,
    )
    np.testing.assert_array_equal(
        loaded.ground_track_source.segment_ids, loaded.series.segment_ids
    )


def test_playback_cursor_can_override_oem_interpolation_metadata() -> None:
    jp_sat_oem_path = (
        Path(__file__).resolve().parents[2] / "data" / "JPSS-1_small.15m.oem"
    )
    oem_data, timestamps_s, states_m = read_oem_states(jp_sat_oem_path)
    assert oem_data.meta.interpolation == "Lagrange"
    assert oem_data.meta.interpolation_degree == 5

    loaded_from_metadata = load_playback_data(
        jp_sat_oem_path, use_oem_interpolation=True
    )
    metadata_cursor = OemCursor(
        timestamps_s,
        states_m,
        interpolation=oem_data.meta.interpolation,
        interpolation_degree=oem_data.meta.interpolation_degree,
        segment_ids=oem_data.segment_ids[: len(timestamps_s)],
    )
    loaded = load_playback_data(jp_sat_oem_path)
    reference_cursor = OemCursor(
        timestamps_s,
        states_m,
        interpolation="hermite",
        interpolation_degree=5,
        segment_ids=oem_data.segment_ids[: len(timestamps_s)],
    )
    midpoint = (timestamps_s[0] + timestamps_s[1]) / 2.0

    np.testing.assert_allclose(
        loaded_from_metadata.cursor.lookup(midpoint).state_m,
        metadata_cursor.lookup(midpoint).state_m,
    )
    np.testing.assert_allclose(
        loaded.cursor.lookup(midpoint).state_m,
        reference_cursor.lookup(midpoint).state_m,
    )


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
    computed = compute_orbit_series(timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1])

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
    computed = compute_orbit_series(timestamps, states, TimeUnit.MINUTES, [0, 0, 1, 1])
    view = SpeedAltitudeView(timestamps[0])
    figure = view.build(computed, TimeUnit.MINUTES)
    try:
        for axes in figure.axes:
            series_lines = [
                line for line in axes.lines if line.get_label() != "_child0"
            ]
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
