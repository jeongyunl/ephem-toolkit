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


def test_resolve_time_bound_accepts_absolute_iso8601() -> None:
    resolved_epoch_s = diff_oem._resolve_time_bound(
        "1970-01-01T00:16:40Z", 0.0
    )

    assert resolved_epoch_s == 1_000.0


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
