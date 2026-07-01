"""Regression tests for :mod:`interpolator.lagrange`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

import common.oem as oem
from interpolator.lagrange import LagrangeInterpolator


def test_lagrange_interpolator_interpolates_linear_data() -> None:
    interpolator = LagrangeInterpolator(dimension=2, degree=8)
    for x in range(10):
        interpolator.add_point(float(x), np.array([float(x), float(x)], dtype=float))

    success, estimated = interpolator.interpolate(4.5)
    assert success is True
    assert estimated == pytest.approx([4.5, 4.5])


def test_interpolated_oem_velocity_norm_matches_original_oem() -> None:
    """Should interpolate OEM states and preserve velocity norm accuracy."""

    number_of_data_points = 80
    step_size_sec = 2.0
    interpolation_degree = 6

    test_dir = Path(__file__).parent
    oem_path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header, meta, all_states = oem.read_oem(oem_path)
    all_timestamps = sorted(all_states)
    first_n_timestamps = all_timestamps[:number_of_data_points]

    interpolator = LagrangeInterpolator(dimension=6, degree=interpolation_degree)
    for timestamp in first_n_timestamps:
        interpolator.add_point(timestamp, all_states[timestamp])

    start_time = first_n_timestamps[0]
    end_time = first_n_timestamps[-1]

    previous_interpolated_position = np.asarray(all_states[start_time][0:3])

    evaluation_times = np.arange((start_time + step_size_sec), end_time, step_size_sec)

    for time in evaluation_times:
        success, interpolated_state = interpolator.interpolate(time)
        assert success is True

        nearest_idx = int(np.argmin(np.abs(np.asarray(first_n_timestamps) - time)))
        reference_timestamp = first_n_timestamps[nearest_idx]
        reference_velocity_norm = np.linalg.norm(all_states[reference_timestamp][3:6])

        # Calculate velocity using two adjacent interpolated positions
        interpolated_position = np.asarray(interpolated_state[0:3])
        calculated_velocity_norm_from_interpolated_positions = (
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

        interpolated_velocity = np.asarray(interpolated_state[3:6])
        interpolated_velocity_norm = np.linalg.norm(interpolated_velocity)

        assert abs(interpolated_velocity_norm - reference_velocity_norm) < 1e-2

        previous_interpolated_position = interpolated_position


def test_independent_variable_range() -> None:
    number_of_data_points = 40

    test_dir = Path(__file__).parent
    oem_path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header, meta, states = oem.read_oem(oem_path)
    timestamps = sorted(states)
    first_n_timestamps = timestamps[:number_of_data_points]

    interpolator = LagrangeInterpolator(dimension=6, degree=8)
    for timestamp in first_n_timestamps:
        interpolator.add_point(timestamp, states[timestamp])

    start_time = first_n_timestamps[0]
    end_time = first_n_timestamps[-1]

    # Bounds test

    success, estimated = interpolator.interpolate(start_time - 10.0)
    assert success == False and estimated == None

    success, estimated = interpolator.interpolate(start_time)
    assert success is True and estimated is not None

    success, estimated = interpolator.interpolate(start_time + 10.0)
    assert success is True and estimated is not None

    success, estimated = interpolator.interpolate(end_time - 10.0)
    assert success is True and estimated is not None

    success, estimated = interpolator.interpolate(end_time)
    assert success is True and estimated is not None

    success, estimated = interpolator.interpolate(end_time + 10.0)
    assert success == False and estimated == None


def test_internal_cache_validity() -> None:
    """Should interpolate OEM states and preserve velocity norm accuracy."""

    number_of_data_points = 80
    step_size_sec = 5.0

    test_dir = Path(__file__).parent
    oem_path = test_dir / "data" / "ISS_2026-05-20.OEM"

    header, meta, all_states = oem.read_oem(oem_path)
    all_timestamps = sorted(all_states)
    first_n_timestamps = all_timestamps[:number_of_data_points]

    interpolator = LagrangeInterpolator(dimension=6, degree=8)
    for timestamp in first_n_timestamps:
        interpolator.add_point(timestamp, all_states[timestamp])

    start_time = first_n_timestamps[0]
    end_time = first_n_timestamps[-1]

    previous_interpolated_position = np.asarray(all_states[start_time][0:3])

    evaluation_times = np.arange((start_time + step_size_sec), end_time, step_size_sec)

    interpolated_states = {}

    for time in evaluation_times:
        success, interpolated_state = interpolator.interpolate(time)
        assert success is True
        interpolated_states[time] = interpolated_state

    import random

    shuffled_times = evaluation_times.tolist()
    random.shuffle(shuffled_times)

    for time in shuffled_times:
        success, interpolated_state = interpolator.interpolate(time)
        assert success is True
        np.testing.assert_allclose(
            interpolated_state, interpolated_states[time], atol=1e-10
        )


def test_closest_data_index_validity_check() -> None:
    interpolator = LagrangeInterpolator(dimension=1, degree=4)
    for x in range(5):
        interpolator.add_point(float(x), np.array([float(x)], dtype=float))

    interpolator.closest_data_index = 2
    assert interpolator.is_closest_data_index_valid(2.4) is True
    assert interpolator.is_closest_data_index_valid(1.4) is False
    assert interpolator.is_closest_data_index_valid(3.6) is False
    interpolator.closest_data_index = 0
    assert interpolator.is_closest_data_index_valid(0.4) is True
    assert interpolator.is_closest_data_index_valid(-0.1) is True
