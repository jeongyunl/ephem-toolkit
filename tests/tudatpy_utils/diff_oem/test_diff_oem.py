"""Tests for the diff_oem comparison and interpolation options."""

from __future__ import annotations

import numpy as np
import pytest

from tudatpy_utils.core.interpolator import lagrange
from tudatpy_utils.diff_oem import cli
from tudatpy_utils.diff_oem import comparison
from tudatpy_utils.diff_oem import data_structures
from tudatpy_utils.diff_oem import output
from tudatpy_utils.diff_oem import transformation_stages
from tudatpy_utils.diff_oem import utils


def _create_state(epoch_s: float, state_value: float) -> tuple[float, np.ndarray]:
    """Create a synthetic state at the specified epoch."""
    return (
        epoch_s,
        np.full(6, state_value, dtype=float),
    )


def _reference_interpolator() -> lagrange.LagrangeInterpolator:
    """Create a degree-8 interpolator for synthetic linear states."""
    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=7
    )
    reference_states: list[tuple[float, np.ndarray]] = [
        _create_state(float(index), float(index)) for index in range(8)
    ]
    interpolator.set_data(reference_states)
    return interpolator


def test_find_overlapping_time_range() -> None:
    reference_states: list[tuple[float, np.ndarray]] = [
        _create_state(float(index), float(index)) for index in range(5)
    ]
    comparison_states: list[tuple[float, np.ndarray]] = [
        _create_state(float(index), float(index)) for index in range(2, 7)
    ]

    assert utils.find_overlapping_time_range(reference_states, comparison_states) == (
        2.0,
        4.0,
    )
    assert (
        utils.find_overlapping_time_range(
            reference_states,
            [_create_state(10.0, 10.0)],
        )
        is None
    )


def test_resolve_time_bound_accepts_reference_relative_duration() -> None:
    reference_epoch_s = 1_000.0

    assert utils.resolve_time_bound("2m", reference_epoch_s) == 1_120.0


def test_stop_duration_is_relative_to_resolved_start() -> None:
    reference_epoch_s = 1_000.0
    start_epoch_s = utils.resolve_time_bound("10m", reference_epoch_s)

    assert utils.resolve_time_bound("2m", start_epoch_s) == 1_720.0


def test_resolve_time_bound_accepts_absolute_iso8601() -> None:
    resolved_epoch_s = utils.resolve_time_bound("1970-01-01T00:16:40Z", 0.0)

    assert resolved_epoch_s == 1_000.0


def test_parse_rotation_fit_span_uses_duration_parser() -> None:
    assert utils.parse_rotation_fit_span("1h30m") == 5_400.0


def test_parse_rotation_fit_span_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError):
        utils.parse_rotation_fit_span("0s")
    with pytest.raises(ValueError):
        utils.parse_rotation_fit_span("-5m")


def test_extract_stage_sequence_preserves_repeated_transformations() -> None:
    assert cli.extract_stage_sequence(
        ["--rot", "--time-shift", "--rot", "--time-shift"]
    ) == ["rot", "time_shift", "rot", "time_shift"]


def test_compare_states_interpolates_reference_at_comparison_epoch() -> None:
    result: data_structures.ComparisonResult = comparison.compare_states(
        _create_state(0.0, 0.0),
        _create_state(3.5, 3.5),
        _reference_interpolator(),
    )

    assert result.reference_epoch == result.comparison_epoch
    assert result.time_diff_s is None
    np.testing.assert_allclose(result.position_diff_km, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(result.velocity_diff_km_s, np.zeros(3), atol=1e-12)


def test_compare_states_rejects_comparison_epoch_outside_reference_range() -> None:
    with pytest.raises(
        ValueError, match="outside the reference OEM interpolation range"
    ):
        comparison.compare_states(
            _create_state(0.0, 0.0),
            _create_state(8.0, 8.0),
            _reference_interpolator(),
        )


def test_compare_states_interpolates_comparison_at_reference_epoch() -> None:
    result = comparison.compare_states(
        _create_state(3.5, 3.5),
        _create_state(0.0, 0.0),
        comparison_interpolator=_reference_interpolator(),
    )

    assert result.reference_epoch == result.comparison_epoch
    assert result.time_diff_s is None
    np.testing.assert_allclose(result.position_diff_km, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(result.velocity_diff_km_s, np.zeros(3), atol=1e-12)


def test_compare_states_calculates_reference_rtn_coordinates() -> None:
    reference_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
    comparison_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0]))

    result = comparison.compare_states(reference_state, comparison_state)

    np.testing.assert_allclose(result.rtn_position_km, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(
        result.rtn_velocity_km_s,
        np.array([0.0, 0.001, 0.0]),
        atol=1e-12,
    )


def test_fit_rotation_matrix_matches_comparison_to_reference() -> None:
    angle_rad = np.deg2rad(30.0)
    reference_rotation = np.array(
        [
            [np.cos(angle_rad), -np.sin(angle_rad), 0.0],
            [np.sin(angle_rad), np.cos(angle_rad), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    reference_states = [
        (
            float(index),
            np.array(
                [
                    7.0 + index,
                    2.0 * index,
                    3.0 - index,
                    0.1 * index,
                    7.5 - index,
                    0.3 + 0.2 * index,
                ]
            ),
        )
        for index in range(3)
    ]
    comparison_states = [
        (
            epoch_s,
            np.concatenate(
                [
                    reference_rotation.T @ state_m[0:3],
                    np.array([91.0 + epoch_s, -37.0, 12.0]),
                ]
            ),
        )
        for epoch_s, state_m in reference_states
    ]
    fitted_rotation = transformation_stages.RotationStage._fit_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-12)
    result = comparison.compare_states(
        reference_states[0],
        comparison_states[0],
        comparison_rotation_matrix=fitted_rotation,
    )
    np.testing.assert_allclose(result.position_diff_km, np.zeros(3), atol=1e-12)


def test_fit_xy_rotation_matrix_matches_comparison_to_reference() -> None:
    reference_rotation = transformation_stages.RotationXYStage._rotation_matrix_y(
        np.deg2rad(-12.0)
    ) @ (transformation_stages.RotationXYStage._rotation_matrix_x(np.deg2rad(7.0)))
    reference_states = [
        (
            float(index),
            np.array(
                [
                    7.0 + index,
                    2.0 * index,
                    3.0 - index,
                    0.1 * index,
                    7.5 - index,
                    0.3 + 0.2 * index,
                ]
            ),
        )
        for index in range(3)
    ]
    comparison_states = [
        (
            epoch_s,
            np.concatenate(
                [
                    reference_rotation.T @ state_m[0:3],
                    np.array([91.0 + epoch_s, -37.0, 12.0]),
                ]
            ),
        )
        for epoch_s, state_m in reference_states
    ]

    fitted_rotation = transformation_stages.RotationXYStage._fit_xy_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-9)


def test_fit_z_rotation_matrix_matches_comparison_to_reference() -> None:
    reference_rotation = transformation_stages.RotationZStage._rotation_matrix_z(
        np.deg2rad(23.0)
    )
    reference_states = [
        (
            float(index),
            np.array(
                [
                    7.0 + index,
                    2.0 * index,
                    3.0 - index,
                    0.1 * index,
                    7.5 - index,
                    0.3 + 0.2 * index,
                ]
            ),
        )
        for index in range(3)
    ]
    comparison_states = [
        (
            epoch_s,
            np.concatenate(
                [
                    reference_rotation.T @ state_m[0:3],
                    np.array([91.0 + epoch_s, -37.0, 12.0]),
                ]
            ),
        )
        for epoch_s, state_m in reference_states
    ]

    fitted_rotation = transformation_stages.RotationZStage._fit_z_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-9)


def test_print_statistics_reports_default_criteria(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = comparison.compare_states(
        (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0])),
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0])),
    )

    output.ComparisonOutput(
        comparison_results=[(0.0, result)],
        reference_interpolator=None,
        comparison_interpolator=None,
        verbose=False,
        rtn=False,
    ).print_statistics(include_time_difference=True)

    captured_output = capsys.readouterr().out
    assert "Statistics (mean, std, min, max)" in captured_output
    assert "time difference (s): +1, +0, +1, +1" in captured_output
    assert "position difference (km): +0.000, +0.000, +0.000, +0.000" in captured_output
    assert (
        "velocity difference (km/s): +0.001000, +0.000000, +0.001000, +0.001000"
        in captured_output
    )


def test_print_statistics_reports_rtn_criteria(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
    first_result = comparison.compare_states(
        reference_state,
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0])),
    )
    second_result = comparison.compare_states(
        reference_state,
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 3.0, 0.0])),
    )

    output.ComparisonOutput(
        comparison_results=[(0.0, first_result), (0.0, second_result)],
        reference_interpolator=None,
        comparison_interpolator=None,
        verbose=False,
        rtn=True,
    ).print_statistics(
        include_time_difference=False,
    )

    captured_output = capsys.readouterr().out
    assert "Statistics (std, min, max)" in captured_output
    assert "RTN r (km): +0.000, +0.000, +0.000" in captured_output
    assert "RTN v" not in captured_output
