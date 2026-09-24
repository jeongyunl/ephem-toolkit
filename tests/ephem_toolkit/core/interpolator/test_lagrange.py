"""Tests for core/interpolator/lagrange.py — Lagrange interpolation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.ccsds.oem import CcsdsOem
import core.interpolator.lagrange as lagrange


def test_lagrange_interpolator_interpolates_linear_data() -> None:
    """Test that Lagrange interpolator correctly interpolates linear data."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=2, degree=7
    )
    for x in range(10):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(x)], dtype=float)
        )

    estimated: np.ndarray = interpolator.interpolate(4.5)
    assert estimated == pytest.approx([4.5, 4.5])


def test_lagrange_interpolator_adjusts_degree_for_short_data() -> None:
    """Test interpolation when fewer samples than the requested degree exist."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=2, degree=7
    )
    # With 7 points, max degree is 6 (N-1 for N points)
    for x in range(7):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(2 * x)], dtype=float)
        )

    estimated: np.ndarray | None = interpolator.interpolate(5.5)
    assert estimated == pytest.approx([5.5, 11.0])


def test_interpolated_oem_velocity_norm_matches_original_oem() -> None:
    """Test that interpolated OEM states preserve velocity norm accuracy."""

    number_of_data_points: int = 80
    step_size_sec: float = 2.0
    interpolation_degree: int = 7

    test_dir: Path = Path(__file__).parents[3]
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20_small.OEM"

    all_states_float: list[tuple[float, np.ndarray]] = CcsdsOem.read(oem_path).states
    # Convert to dict for easier access by timestamp
    all_states_dict: dict[float, np.ndarray] = {
        ts: state for ts, state in all_states_float
    }
    all_timestamps: list = [ts for ts, _ in all_states_float]
    first_n_timestamps: list[float] = all_timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=interpolation_degree
    )
    # Use list of tuples (already sorted)
    interpolator.set_data(all_states_float[:number_of_data_points])

    start_time: float = first_n_timestamps[0]
    end_time: float = first_n_timestamps[-1]

    previous_interpolated_position: np.ndarray = np.asarray(
        all_states_dict[start_time][0:3]
    )

    evaluation_times: np.ndarray = np.arange(
        (start_time + step_size_sec), end_time, step_size_sec
    )

    for time in evaluation_times:
        interpolated_state: np.ndarray = interpolator.interpolate(time)

        nearest_idx: int = int(np.argmin(np.abs(np.asarray(first_n_timestamps) - time)))
        reference_timestamp: float = first_n_timestamps[nearest_idx]
        reference_velocity_norm: float = np.linalg.norm(
            all_states_dict[reference_timestamp][3:6]
        )

        # Calculate velocity using two adjacent interpolated positions
        interpolated_position: np.ndarray = np.asarray(interpolated_state[0:3])
        calculated_velocity_norm_from_interpolated_positions: float = (
            np.linalg.norm(interpolated_position - previous_interpolated_position)
            / step_size_sec
        )

        # Tolerance adjusted for m/s units (was 1e-2 for km/s, now 10.0 for m/s)
        assert (
            abs(
                calculated_velocity_norm_from_interpolated_positions
                - reference_velocity_norm
            )
            < 10.0
        )

        interpolated_velocity: np.ndarray = np.asarray(interpolated_state[3:6])
        interpolated_velocity_norm: float = np.linalg.norm(interpolated_velocity)

        assert abs(interpolated_velocity_norm - reference_velocity_norm) < 10.0

        previous_interpolated_position = interpolated_position


def test_independent_variable_range() -> None:
    """Test that interpolator respects independent variable range bounds."""
    number_of_data_points: int = 40

    test_dir: Path = Path(__file__).parents[3]
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20_small.OEM"

    states_float: list[tuple[float, np.ndarray]] = CcsdsOem.read(oem_path).states
    timestamps: list = [ts for ts, _ in states_float]
    first_n_timestamps: list[float] = timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=7
    )
    for timestamp, state in states_float[:number_of_data_points]:
        interpolator.add_data_point(timestamp, state)

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

    test_dir: Path = Path(__file__).parents[3]
    oem_path: Path = test_dir / "data" / "ISS_2026-05-20_small.OEM"

    all_states_float: list[tuple[float, np.ndarray]] = CcsdsOem.read(oem_path).states
    # Convert to dict for easier access by timestamp
    all_states_dict: dict[float, np.ndarray] = {
        ts: state for ts, state in all_states_float
    }
    all_timestamps: list = [ts for ts, _ in all_states_float]
    first_n_timestamps: list[float] = all_timestamps[:number_of_data_points]

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=7
    )
    for timestamp, state in all_states_float[:number_of_data_points]:
        interpolator.add_data_point(timestamp, state)

    start_time: float = first_n_timestamps[0]
    end_time: float = first_n_timestamps[-1]

    previous_interpolated_position: np.ndarray = np.asarray(
        all_states_dict[start_time][0:3]
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
            interpolated_state, interpolated_states[time], rtol=1e-6, atol=1e-6
        )


def test_public_interpolation_boundary_behavior() -> None:
    """Test that public interpolation API behaves correctly at boundaries and inside range."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=1, degree=4
    )
    for x in range(5):
        interpolator.add_data_point(float(x), np.array([float(x)], dtype=float))

    assert interpolator.interpolate(2.4) == pytest.approx(2.4)
    assert interpolator.interpolate(1.4) == pytest.approx(1.4)
    assert interpolator.interpolate(3.6) == pytest.approx(3.6)
    assert interpolator.interpolate(-0.1) is None
    assert interpolator.interpolate(4.1) is None


@pytest.mark.parametrize(
    ("boundary_mode", "expected_window_size"),
    [("centered", 5), ("widen", 7), ("edge", 7), ("compact", 3)],
)
def test_lagrange_boundary_modes_select_expected_extrapolation_windows(
    boundary_mode: str, expected_window_size: int
) -> None:
    interpolator = lagrange.LagrangeInterpolator(
        dimension=1,
        degree=4,
        boundary_mode=boundary_mode,
        boundary_window_extension=2,
    )
    for x_value in range(10):
        interpolator.add_data_point(float(x_value), np.array([float(x_value)]))

    interpolator.allow_extrapolation = True
    start_index, left_window = interpolator._select_window(-1.0)
    end_index, right_window = interpolator._select_window(10.0)

    assert start_index == 0
    assert len(left_window) == expected_window_size
    assert end_index == 10 - expected_window_size
    assert len(right_window) == expected_window_size


def test_lagrange_interpolator_validates_configuration() -> None:
    with pytest.raises(ValueError, match="degree must be at least 1"):
        lagrange.LagrangeInterpolator(degree=0)
    with pytest.raises(ValueError, match="boundary_mode"):
        lagrange.LagrangeInterpolator(boundary_mode="invalid")
    with pytest.raises(ValueError, match="extension must be non-negative"):
        lagrange.LagrangeInterpolator(boundary_window_extension=-1)


def test_lagrange_interpolator_invalidates_cached_window_after_new_data() -> None:
    interpolator = lagrange.LagrangeInterpolator(dimension=1, degree=2)
    for x_value in range(4):
        interpolator.add_data_point(float(x_value), np.array([float(x_value)]))

    interpolator.interpolate(1.5)
    assert interpolator._cache_window_start >= 0

    interpolator.add_data_point(4.0, np.array([4.0]))
    assert interpolator._cache_window_start == -1
    assert interpolator._cache_window_values is None

    interpolator.clear_storage()
    assert interpolator.independent_values == []
    assert interpolator.dependent_values == []
    assert interpolator._cache_window_start == -1
