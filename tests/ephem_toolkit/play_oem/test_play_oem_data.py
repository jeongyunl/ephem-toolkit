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
        np.testing.assert_allclose(
            getattr(play_series, field.name),
            getattr(plot_series, field.name),
            err_msg=f"Mismatch in derived series field {field.name}",
        )


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
