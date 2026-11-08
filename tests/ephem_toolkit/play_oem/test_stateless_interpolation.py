"""Tests for interpolation over store-owned sample views."""

from __future__ import annotations

import gc
import weakref

import numpy as np
import pytest

from ephem_toolkit.core.interpolator import Interpolator
from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.play_oem.cursor import OemCursor


def _sample_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    timestamps_s = np.concatenate((np.arange(11.0), np.arange(14.0, 25.0)))
    scaled_time = timestamps_s / 10.0
    states_m = np.column_stack(
        (
            7_000_000.0 + 1_000.0 * scaled_time**2,
            2_000_000.0 + 500.0 * np.sin(scaled_time),
            1_000_000.0 + 200.0 * scaled_time**3,
            1_000.0 + 2.0 * scaled_time,
            7_000.0 * np.cos(scaled_time),
            300.0 * scaled_time**2,
        )
    )
    segment_ids = np.concatenate(
        (np.zeros(11, dtype=int), np.ones(11, dtype=int))
    )
    return timestamps_s, states_m, segment_ids


def _interpolator(method: str, degree: int | None) -> Interpolator:
    spec = (
        None
        if method == "linear"
        else InterpolationSpec(InterpolationType(method), degree=degree)
    )
    return InterpolatorFactory.create(
        spec,
        dimension=6,
        is_cartesian_state=method == "hermite",
        stateless=True,
    )


@pytest.mark.parametrize(
    ("method", "degree"),
    [
        ("linear", None),
        ("hermite", 5),
        ("lagrange", 4),
        ("chebyshev", 3),
    ],
)
def test_stateless_evaluator_matches_cursor_at_samples_edges_and_gaps(
    method: str, degree: int | None
) -> None:
    timestamps_s, states_m, segment_ids = _sample_data()
    cursor = OemCursor(
        timestamps_s,
        states_m,
        interpolation=method,
        interpolation_degree=degree,
        segment_ids=segment_ids,
    )
    evaluator = _interpolator(method, degree)

    for query_time_s in (
        0.0,
        0.25,
        5.5,
        10.0,
        10.5,
        12.0,
        14.0,
        14.25,
        20.5,
        24.0,
        24.5,
    ):
        expected = cursor.lookup(query_time_s).state_m
        actual = evaluator.interpolate_view(
            timestamps_s, states_m, query_time_s, segment_ids
        )
        if expected is None:
            assert actual is None
        else:
            assert actual is not None
            np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-9)


def test_policy_changes_select_new_stateless_interpolation_strategy() -> None:
    timestamps_s, states_m, segment_ids = _sample_data()
    cursor = OemCursor(timestamps_s, states_m, segment_ids=segment_ids)
    query_time_s = 5.25

    for method, degree in (("linear", None), ("hermite", 5), ("lagrange", 3)):
        cursor.set_interpolation(method, degree)
        evaluator = _interpolator(method, degree)
        actual = evaluator.interpolate_view(
            timestamps_s, states_m, query_time_s, segment_ids
        )
        expected = cursor.lookup(query_time_s).state_m
        assert actual is not None
        assert expected is not None
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-9)


def test_exact_sample_is_a_read_only_view_of_the_input_state() -> None:
    timestamps_s, states_m, segment_ids = _sample_data()
    actual = InterpolatorFactory.create(
        None, dimension=6, stateless=True
    ).interpolate_view(
        timestamps_s, states_m, 5.0, segment_ids
    )

    assert actual is not None
    assert np.shares_memory(actual, states_m)
    assert not actual.flags.writeable
    with pytest.raises(ValueError):
        actual[0] = 0.0


def test_stateless_mode_cannot_be_disabled_after_configuration() -> None:
    evaluator = InterpolatorFactory.create(None, dimension=6, stateless=True)

    with pytest.raises(AttributeError):
        evaluator.stateless = False


def test_core_stateless_interpolator_accepts_generic_dependent_dimensions() -> None:
    timestamps_s = np.array([0.0, 1.0, 2.0])
    values = np.array([[0.0, 1.0], [1.0, 1.0], [4.0, 1.0]])
    evaluator = InterpolatorFactory.create(
        InterpolationSpec(InterpolationType.LAGRANGE, degree=2),
        dimension=2,
        stateless=True,
    )

    actual = evaluator.interpolate_view(timestamps_s, values, 1.5)

    assert actual is not None
    np.testing.assert_allclose(actual, [2.25, 1.0], rtol=1e-12, atol=1e-12)


def test_interpolator_does_not_retain_input_arrays() -> None:
    timestamps_s, states_m, segment_ids = _sample_data()
    timestamp_ref = weakref.ref(timestamps_s)
    state_ref = weakref.ref(states_m)
    segment_ref = weakref.ref(segment_ids)
    evaluator = _interpolator("hermite", 3)

    result = evaluator.interpolate_view(timestamps_s, states_m, 5.25, segment_ids)
    assert result is not None
    assert evaluator.independent_values == []
    assert evaluator.dependent_values == []
    del result, timestamps_s, states_m, segment_ids
    gc.collect()

    assert timestamp_ref() is None
    assert state_ref() is None
    assert segment_ref() is None


def test_large_dataset_evaluation_materializes_only_support_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_count = 100_000
    timestamps_s = np.arange(sample_count, dtype=float)
    scaled_time = timestamps_s / sample_count
    states_m = np.column_stack(
        (
            7_000_000.0 + scaled_time,
            2_000_000.0 + scaled_time**2,
            1_000_000.0 + scaled_time**3,
            scaled_time,
            scaled_time**2,
            scaled_time**3,
        )
    )
    segment_ids = np.zeros(sample_count, dtype=int)
    evaluator = _interpolator("chebyshev", 5)
    bounded_element_count = 64
    original_interpolate = evaluator.interpolate

    def check_support_before_interpolation(query_value):
        assert len(evaluator.independent_values) == 6
        assert len(evaluator.dependent_values) == 6
        assert all(
            np.shares_memory(row, states_m) for row in evaluator.dependent_values
        )
        return original_interpolate(query_value)

    original_asarray = np.asarray
    def unexpected_factory_call(*args, **kwargs):
        raise AssertionError("stateless evaluation recreated its interpolator")

    def bounded_asarray(values, *args, **kwargs):
        result = original_asarray(values, *args, **kwargs)
        assert result.size <= bounded_element_count
        return result

    monkeypatch.setattr(evaluator, "interpolate", check_support_before_interpolation)
    monkeypatch.setattr(InterpolatorFactory, "create", staticmethod(unexpected_factory_call))
    monkeypatch.setattr(np, "asarray", bounded_asarray)

    assert evaluator.stateless
    result = evaluator.interpolate_view(timestamps_s, states_m, 50_000.25, segment_ids)
    second_result = evaluator.interpolate_view(
        timestamps_s, states_m, 50_000.5, segment_ids
    )

    assert result is not None
    assert result.shape == (6,)
    assert second_result is not None
    assert evaluator.independent_values == []
    assert evaluator.dependent_values == []


@pytest.mark.parametrize(
    ("spec", "dimension", "is_cartesian_state", "message"),
    [
        (InterpolationSpec(InterpolationType.HERMITE, degree=-1), 6, True, "degree"),
        (None, 0, False, "dimension"),
        (None, True, False, "dimension"),
        (InterpolationSpec(InterpolationType.HERMITE), 3, True, "dimension must be 6"),
    ],
)
def test_invalid_interpolation_policy_is_rejected(
    spec: InterpolationSpec | None,
    dimension: int,
    is_cartesian_state: bool,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        InterpolatorFactory.create(
            spec,
            dimension,
            is_cartesian_state,
            stateless=True,
        )


def test_stateful_interpolator_rejects_view_evaluation() -> None:
    interpolator = InterpolatorFactory.create(
        InterpolationSpec(InterpolationType.LAGRANGE, degree=2),
        dimension=2,
    )

    with pytest.raises(RuntimeError, match="requires stateless mode"):
        interpolator.interpolate_view(
            np.array([0.0, 1.0, 2.0]),
            np.array([[0.0, 0.0], [1.0, 1.0], [4.0, 2.0]]),
            1.5,
        )


def test_stateless_factory_rejects_stored_data_and_noncentered_windows() -> None:
    spec = InterpolationSpec(InterpolationType.LAGRANGE, degree=2)

    with pytest.raises(ValueError, match="cannot be created with stored data"):
        InterpolatorFactory.create(spec, stateless=True, data=[])
    with pytest.raises(ValueError, match="requires centered windows"):
        InterpolatorFactory.create(spec, stateless=True, boundary_mode="edge")


@pytest.mark.parametrize(
    "interpolation_type",
    [
        InterpolationType.HERMITE,
        InterpolationType.LAGRANGE,
        InterpolationType.CHEBYSHEV,
    ],
)
def test_replacing_samples_invalidates_interpolator_cache(
    interpolation_type: InterpolationType,
) -> None:
    timestamps = np.arange(6.0)
    original_values = timestamps**2
    replacement_values = original_values + 10.0
    spec = InterpolationSpec(interpolation_type, degree=3)
    interpolator = InterpolatorFactory.create(spec, dimension=1)

    interpolator.set_data(
        list(zip(timestamps.tolist(), original_values[:, None]))
    )
    original_result = interpolator.interpolate(2.5)
    interpolator.set_data(
        list(zip(timestamps.tolist(), replacement_values[:, None]))
    )
    replacement_result = interpolator.interpolate(2.5)

    assert original_result is not None
    assert replacement_result is not None
    np.testing.assert_allclose(
        replacement_result,
        original_result + 10.0,
        rtol=1e-8,
        atol=1e-8,
    )
