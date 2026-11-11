"""Tests for direction-independent play-oem cursor lookup."""

from __future__ import annotations

import numpy as np
import pytest

from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.play_oem.cursor import CursorStatus, StoreCursor
from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from tests.ephem_toolkit.play_oem.cursor_helpers import make_store_cursor


@pytest.fixture
def sample_states() -> tuple[list[float], list[np.ndarray]]:
    times_s = [0.0, 1.0, 2.0, 3.0]
    states_m = [
        np.array(
            [
                7_000_000.0 + time * 100.0,
                time * 200.0,
                time * 300.0,
                0.0,
                7_500.0 + time,
                0.0,
            ]
        )
        for time in times_s
    ]
    return times_s, states_m


def test_lookup_returns_exact_sample_and_derived_values(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    times_s, states_m = sample_states
    _, cursor = make_store_cursor(times_s, states_m)

    result = cursor.lookup(1.0)

    assert result.status is CursorStatus.EXACT_SAMPLE
    np.testing.assert_array_equal(result.state_m, states_m[1])
    np.testing.assert_allclose(result.r_km, states_m[1][:3] * 0.001)
    np.testing.assert_allclose(result.v_kms, states_m[1][3:] * 0.001)
    assert result.speed == pytest.approx(np.linalg.norm(result.v_kms))
    assert result.distance == pytest.approx(np.linalg.norm(result.r_km))
    assert result.altitude is not None


def test_store_cursor_uses_read_only_raw_views_and_refreshes_prefix() -> None:
    store = OemDataStore()
    epoch = store.begin(3)
    first = store.reserve(2)
    first.raw[:] = (
        (0.0, 7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0),
        (1.0, 7_000_100.0, 200.0, 300.0, 0.0, 7_501.0, 0.0),
    )
    first.segment_ids[:] = (0, 0)
    store.commit(first, 2)

    snapshot = store.snapshot()
    cursor = StoreCursor(store, snapshot)

    assert np.shares_memory(cursor.timestamps_s, snapshot.raw)
    assert np.shares_memory(cursor.states_m, snapshot.raw)
    assert np.shares_memory(cursor.segment_ids, snapshot.segment_ids)
    assert not cursor.timestamps_s.flags.writeable
    assert not cursor.states_m.flags.writeable
    assert not cursor.segment_ids.flags.writeable
    np.testing.assert_array_equal(cursor.lookup(1.0).state_m, snapshot.raw[1, 1:7])

    second = store.reserve(1, epoch=epoch)
    second.raw[0] = (2.0, 7_000_200.0, 400.0, 600.0, 0.0, 7_502.0, 0.0)
    second.segment_ids[0] = 0
    store.commit(second, 1)
    cursor.refresh(store.snapshot())

    assert cursor.t_end == 2.0
    assert len(cursor.timestamps_s) == 3
    np.testing.assert_array_equal(cursor.lookup(2.0).state_m, cursor.states_m[-1])


def test_store_cursor_rejects_snapshot_from_replaced_epoch() -> None:
    store = OemDataStore()
    store.begin(1)
    reservation = store.reserve(1)
    reservation.raw[0] = (1.0, 7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0)
    reservation.segment_ids[0] = 0
    store.commit(reservation, 1)
    cursor = StoreCursor(store, store.snapshot())

    store.begin(1)

    with pytest.raises(RuntimeError, match="epoch has changed"):
        cursor.refresh(store.snapshot())


def test_lookup_linearly_interpolates_state_when_metadata_is_absent(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    times_s, states_m = sample_states
    _, cursor = make_store_cursor(times_s, states_m)

    result = cursor.lookup(1.5)

    assert result.status is CursorStatus.INTERPOLATED
    np.testing.assert_allclose(result.state_m, (states_m[1] + states_m[2]) / 2.0)


def test_lookup_uses_core_interpolator_when_oem_metadata_is_present(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    times_s, states_m = sample_states
    spec = InterpolationSpec(InterpolationType.LAGRANGE, degree=2)
    interpolator = InterpolatorFactory.create(
        spec=spec,
        dimension=6,
        is_cartesian_state=True,
        data=list(zip(times_s, states_m)),
    )
    _, cursor = make_store_cursor(
        times_s, states_m, interpolation="LAGRANGE", interpolation_degree=2
    )

    result = cursor.lookup(1.5)

    assert result.status is CursorStatus.INTERPOLATED
    np.testing.assert_allclose(result.state_m, interpolator.interpolate(1.5))


def test_lookup_is_identical_when_time_is_reached_in_any_order() -> None:
    times_s = [float(index) for index in range(6)]
    states_m = [
        np.array(
            [
                7_000_000.0 + time**2 * 100.0,
                time**2 * 200.0,
                time**2 * 300.0,
                time**2 * 10.0,
                7_500.0 + time**2 * 3.0,
                time**2 * 4.0,
            ]
        )
        for time in times_s
    ]
    _, cursor = make_store_cursor(
        times_s, states_m, interpolation="LAGRANGE", interpolation_degree=2
    )
    query_times = [0.5, 1.5, 2.5, 3.5, 4.5]

    forward = {t: cursor.lookup(t).state_m for t in query_times}
    backward = {t: cursor.lookup(t).state_m for t in reversed(query_times)}
    random_order = {t: cursor.lookup(t).state_m for t in (2.5, 0.5, 4.5, 1.5, 3.5)}

    for t in query_times:
        np.testing.assert_allclose(backward[t], forward[t])
        np.testing.assert_allclose(random_order[t], forward[t])


def test_lookup_marks_out_of_range_times_unavailable(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    times_s, states_m = sample_states
    _, cursor = make_store_cursor(times_s, states_m)
    out_of_range = cursor.lookup(-1.0)
    assert out_of_range.status is CursorStatus.OUT_OF_RANGE
    assert out_of_range.state_m is None
    assert out_of_range.r_km is None

    _, single_sample_cursor = make_store_cursor([1.0], [states_m[1]])
    unavailable = single_sample_cursor.lookup(1.5)
    assert unavailable.status is CursorStatus.OUT_OF_RANGE
    assert unavailable.state_m is None
    exact = single_sample_cursor.lookup(1.0)
    assert exact.status is CursorStatus.EXACT_SAMPLE


def test_lookup_reports_gap_and_never_interpolates_between_oem_segments(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    _, states_m = sample_states
    _, cursor = make_store_cursor(
        [0.0, 10.0, 100.0, 110.0],
        states_m,
        segment_ids=[0, 0, 1, 1],
    )

    assert cursor.lookup(5.0).status is CursorStatus.INTERPOLATED
    gap_state = cursor.lookup(50.0)
    assert gap_state.status is CursorStatus.GAP
    assert gap_state.state_m is None
    assert gap_state.r_km is None
    assert cursor.lookup(105.0).status is CursorStatus.INTERPOLATED


def test_lookup_rejects_invalid_input_data_and_query(
    sample_states: tuple[list[float], list[np.ndarray]],
) -> None:
    times_s, states_m = sample_states
    with pytest.raises(ValueError, match="strictly increasing"):
        make_store_cursor([0.0, 0.0], states_m[:2])

    _, cursor = make_store_cursor(times_s, states_m)
    with pytest.raises(ValueError, match="query time"):
        cursor.lookup(float("nan"))


def test_empty_store_cursor_is_inert_until_replaced() -> None:
    cursor = StoreCursor.empty()
    store = OemDataStore()
    store.begin(1)

    try:
        assert cursor.t_start == 0.0
        assert cursor.t_end == 0.0
        assert cursor.timestamps_s.shape == (0,)
        assert cursor.states_m.shape == (0, 6)
        assert cursor.segment_ids.shape == (0,)
        assert not cursor.timestamps_s.flags.writeable
        assert not cursor.states_m.flags.writeable
        assert not cursor.segment_ids.flags.writeable
        assert cursor.lookup(12.0).status is CursorStatus.UNAVAILABLE
        with pytest.raises(RuntimeError, match="empty cursor must be replaced"):
            cursor.refresh(store.snapshot())
        with pytest.raises(RuntimeError, match="cannot set interpolation"):
            cursor.set_interpolation("linear", None)
    finally:
        store.close()
