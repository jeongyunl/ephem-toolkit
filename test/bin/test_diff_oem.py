"""Tests for the diff_oem comparison and interpolation options."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_MODULE_PATH = Path(__file__).parents[2] / "bin" / "diff_oem.py"
_MODULE_SPEC = importlib.util.spec_from_file_location("diff_oem", _MODULE_PATH)
assert _MODULE_SPEC is not None
assert _MODULE_SPEC.loader is not None
diff_oem = importlib.util.module_from_spec(_MODULE_SPEC)
sys.modules[_MODULE_SPEC.name] = diff_oem
_MODULE_SPEC.loader.exec_module(diff_oem)


def _state(epoch_s: float, value: float) -> tuple[float, np.ndarray]:
    return (
        epoch_s,
        np.full(6, value, dtype=float),
    )


def _reference_interpolator() -> diff_oem.lagrange.LagrangeInterpolator:
    """Create a degree-8 interpolator for synthetic linear states."""
    interpolator = diff_oem.lagrange.LagrangeInterpolator(dimension=6, degree=8)
    reference_states = [_state(float(index), float(index)) for index in range(8)]
    interpolator.set_data(reference_states)
    return interpolator


def test_get_overlapping_time_range() -> None:
    reference_states = [_state(float(index), float(index)) for index in range(5)]
    comparison_states = [_state(float(index), float(index)) for index in range(2, 7)]

    assert diff_oem._get_overlapping_time_range(
        reference_states, comparison_states
    ) == (2.0, 4.0)
    assert (
        diff_oem._get_overlapping_time_range(
            reference_states,
            [_state(10.0, 10.0)],
        )
        is None
    )


def test_resolve_time_bound_accepts_reference_relative_duration() -> None:
    reference_epoch_s = 1_000.0

    assert diff_oem._resolve_time_bound("2m", reference_epoch_s) == 1_120.0


def test_stop_duration_is_relative_to_resolved_start() -> None:
    reference_epoch_s = 1_000.0
    start_epoch_s = diff_oem._resolve_time_bound("10m", reference_epoch_s)

    assert diff_oem._resolve_time_bound("2m", start_epoch_s) == 1_720.0


def test_resolve_time_bound_accepts_absolute_iso8601() -> None:
    resolved_epoch_s = diff_oem._resolve_time_bound("1970-01-01T00:16:40Z", 0.0)

    assert resolved_epoch_s == 1_000.0


def test_parse_rotation_fit_span_uses_duration_parser() -> None:
    assert diff_oem._parse_rotation_fit_span("1h30m") == 5_400.0


def test_parse_rotation_fit_span_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError):
        diff_oem._parse_rotation_fit_span("0s")
    with pytest.raises(ValueError):
        diff_oem._parse_rotation_fit_span("-5m")


def test_extract_stage_sequence_preserves_repeated_transformations() -> None:
    assert diff_oem._extract_stage_sequence(
        ["--rot", "--time-shift", "--rot", "--time-shift"]
    ) == ["rot", "time_shift", "rot", "time_shift"]


def test_compare_states_interpolates_reference_at_comparison_epoch() -> None:
    result = diff_oem.compare_states(
        _state(0.0, 0.0),
        _state(3.5, 3.5),
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
        diff_oem.compare_states(
            _state(0.0, 0.0),
            _state(8.0, 8.0),
            _reference_interpolator(),
        )


def test_compare_states_interpolates_comparison_at_reference_epoch() -> None:
    result = diff_oem.compare_states(
        _state(3.5, 3.5),
        _state(0.0, 0.0),
        comparison_interpolator=_reference_interpolator(),
    )

    assert result.reference_epoch == result.comparison_epoch
    assert result.time_diff_s is None
    np.testing.assert_allclose(result.position_diff_km, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(result.velocity_diff_km_s, np.zeros(3), atol=1e-12)


def test_compare_states_calculates_reference_rtn_coordinates() -> None:
    reference_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
    comparison_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0]))

    result = diff_oem.compare_states(reference_state, comparison_state)

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
    fitted_rotation = diff_oem.RotationStage._fit_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-12)
    result = diff_oem.compare_states(
        reference_states[0],
        comparison_states[0],
        comparison_rotation_matrix=fitted_rotation,
    )
    np.testing.assert_allclose(result.position_diff_km, np.zeros(3), atol=1e-12)


def test_fit_xy_rotation_matrix_matches_comparison_to_reference() -> None:
    reference_rotation = diff_oem.RotationXYStage._rotation_matrix_y(np.deg2rad(-12.0)) @ (
        diff_oem.RotationXYStage._rotation_matrix_x(np.deg2rad(7.0))
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

    fitted_rotation = diff_oem.RotationXYStage._fit_xy_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-9)


def test_fit_z_rotation_matrix_matches_comparison_to_reference() -> None:
    reference_rotation = diff_oem.RotationZStage._rotation_matrix_z(np.deg2rad(23.0))
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

    fitted_rotation = diff_oem.RotationZStage._fit_z_rotation_matrix(
        list(zip(reference_states, comparison_states))
    )

    np.testing.assert_allclose(fitted_rotation, reference_rotation, atol=1e-9)


def test_print_statistics_reports_default_criteria(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = diff_oem.compare_states(
        (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0])),
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0])),
    )

    diff_oem.ComparisonOutput(
        comparison_results=[(0.0, result)],
        reference_interpolator=None,
        comparison_interpolator=None,
        verbose=False,
        rtn=False,
    ).print_statistics(include_time_difference=True)

    output = capsys.readouterr().out
    assert "Statistics (mean, std, min, max)" in output
    assert "time difference (s): +1, +0, +1, +1" in output
    assert "position difference (km): +0.000, +0.000, +0.000, +0.000" in output
    assert (
        "velocity difference (km/s): +0.001000, +0.000000, +0.001000, +0.001000"
        in output
    )


def test_print_statistics_reports_rtn_criteria(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference_state = (0.0, np.array([1000.0, 0.0, 0.0, 0.0, 1.0, 0.0]))
    first_result = diff_oem.compare_states(
        reference_state,
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 2.0, 0.0])),
    )
    second_result = diff_oem.compare_states(
        reference_state,
        (1.0, np.array([1000.0, 0.0, 0.0, 0.0, 3.0, 0.0])),
    )

    diff_oem.ComparisonOutput(
        comparison_results=[(0.0, first_result), (0.0, second_result)],
        reference_interpolator=None,
        comparison_interpolator=None,
        verbose=False,
        rtn=True,
    ).print_statistics(
        include_time_difference=False,
    )

    output = capsys.readouterr().out
    assert "Statistics (std, min, max)" in output
    assert "RTN r (km): +0.000, +0.000, +0.000" in output
    assert "RTN v" not in output
