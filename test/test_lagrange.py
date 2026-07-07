"""Regression tests for :mod:`interpolator.lagrange`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

import common.oem as oem
import interpolator.lagrange as lagrange


def test_lagrange_interpolator_interpolates_linear_data() -> None:
    """Test that Lagrange interpolator correctly interpolates linear data."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=2, degree=8
    )
    for x in range(10):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(x)], dtype=float)
        )

    estimated: np.ndarray = interpolator.interpolate(4.5)
    assert estimated == pytest.approx([4.5, 4.5])


def test_interpolated_oem_velocity_norm_matches_original_oem() -> None:
    """Test that interpolated OEM states preserve velocity norm accuracy."""

    number_of_data_points: int = 80
    step_size_sec: float = 2.0
    interpolation_degree: int = 6

    test_dir: Path = Path(__file__).parent
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header: dict
    meta: dict
    all_states_float: dict
    header, meta, all_states_float = oem.read_oem(oem_path)
    # all_states_float is now dict[float, np.ndarray] (POSIX timestamps)
    all_timestamps: list = sorted(all_states_float.keys())
    first_n_timestamps: list[float] = all_timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=interpolation_degree
    )
    # Use list of tuples (already sorted) instead of dict comprehension
    interpolator.set_data([(ts, all_states_float[ts]) for ts in first_n_timestamps])

    start_time: float = first_n_timestamps[0]
    end_time: float = first_n_timestamps[-1]

    previous_interpolated_position: np.ndarray = np.asarray(
        all_states_float[start_time][0:3]
    )

    evaluation_times: np.ndarray = np.arange(
        (start_time + step_size_sec), end_time, step_size_sec
    )

    for time in evaluation_times:
        interpolated_state: np.ndarray = interpolator.interpolate(time)

        nearest_idx: int = int(np.argmin(np.abs(np.asarray(first_n_timestamps) - time)))
        reference_timestamp: float = first_n_timestamps[nearest_idx]
        reference_velocity_norm: float = np.linalg.norm(
            all_states_float[reference_timestamp][3:6]
        )

        # Calculate velocity using two adjacent interpolated positions
        interpolated_position: np.ndarray = np.asarray(interpolated_state[0:3])
        calculated_velocity_norm_from_interpolated_positions: float = (
            np.linalg.norm(interpolated_position - previous_interpolated_position)
            / step_size_sec
        )

        assert (
            abs(
                calculated_velocity_norm_from_interpolated_positions
                - reference_velocity_norm
            )
            < 1e-2
        )

        interpolated_velocity: np.ndarray = np.asarray(interpolated_state[3:6])
        interpolated_velocity_norm: float = np.linalg.norm(interpolated_velocity)

        assert abs(interpolated_velocity_norm - reference_velocity_norm) < 1e-2

        previous_interpolated_position = interpolated_position


def test_independent_variable_range() -> None:
    """Test that interpolator respects independent variable range bounds."""
    number_of_data_points: int = 40

    test_dir: Path = Path(__file__).parent
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header: dict
    meta: dict
    states_float: dict
    header, meta, states_float = oem.read_oem(oem_path)
    # states_float is now dict[float, np.ndarray] (POSIX timestamps)
    timestamps: list = sorted(states_float.keys())
    first_n_timestamps: list[float] = timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=8
    )
    for timestamp in first_n_timestamps:
        interpolator.add_data_point(timestamp, states_float[timestamp])

    start_time: float = first_n_timestamps[0]
    end_time: float = first_n_timestamps[-1]

    # Bounds test

    estimated: np.ndarray | None = interpolator.interpolate(start_time - 10.0)
    assert estimated is None

    estimated = interpolator.interpolate(start_time)
    assert estimated is not None

    estimated = interpolator.interpolate(start_time + 10.0)
    assert estimated is not None

    estimated = interpolator.interpolate(end_time - 10.0)
    assert estimated is not None

    estimated = interpolator.interpolate(end_time)
    assert estimated is not None

    estimated = interpolator.interpolate(end_time + 10.0)
    assert estimated is None


def test_internal_cache_integrity() -> None:
    """Test that interpolator cache maintains consistency across repeated queries."""
    number_of_data_points: int = 80
    step_size_sec: float = 5.0

    test_dir: Path = Path(__file__).parent
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header: dict
    meta: dict
    all_states_float: dict
    header, meta, all_states_float = oem.read_oem(oem_path)
    # all_states_float is now dict[float, np.ndarray] (POSIX timestamps)
    all_timestamps: list = sorted(all_states_float.keys())
    first_n_timestamps: list[float] = all_timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=8
    )
    for timestamp in first_n_timestamps:
        interpolator.add_data_point(timestamp, all_states_float[timestamp])

    start_time: float = first_n_timestamps[0]
    end_time: float = first_n_timestamps[-1]

    previous_interpolated_position: np.ndarray = np.asarray(
        all_states_float[start_time][0:3]
    )

    evaluation_times: np.ndarray = np.arange(
        (start_time + step_size_sec), end_time, step_size_sec
    )

    interpolated_states: dict[float, np.ndarray] = {}

    for time in evaluation_times:
        interpolated_state: np.ndarray = interpolator.interpolate(time)
        interpolated_states[time] = interpolated_state

    import random

    shuffled_times: list[float] = evaluation_times.tolist()
    random.shuffle(shuffled_times)

    for time in shuffled_times:
        interpolated_state: np.ndarray = interpolator.interpolate(time)
        np.testing.assert_allclose(
            interpolated_state, interpolated_states[time], atol=1e-10
        )


def test_closest_data_index_validity_check() -> None:
    """Test that closest data index validity check works correctly."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=1, degree=4
    )
    for x in range(5):
        interpolator.add_data_point(float(x), np.array([float(x)], dtype=float))

    interpolator.closest_data_index = 2
    assert interpolator.is_closest_data_index_valid(2.4) is True
    assert interpolator.is_closest_data_index_valid(1.4) is False
    assert interpolator.is_closest_data_index_valid(3.6) is False
    interpolator.closest_data_index = 0
    assert interpolator.is_closest_data_index_valid(0.4) is True
    assert interpolator.is_closest_data_index_valid(-0.1) is True
