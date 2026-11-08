"""Tests for fixed-capacity raw OEM storage."""

from __future__ import annotations

import math
from threading import Event, Thread

import numpy as np
import pytest

from ephem_toolkit.core import misc
from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.chunk_memo import ChunkState
from ephem_toolkit.play_oem.cursor import CursorStatus, OemCursor
from ephem_toolkit.play_oem.oem_data_store import (
    ColumnGroupView,
    InterpolationPolicy,
    LoadStatus,
    OemDataStore,
    RowSpan,
    StoreSnapshot,
)
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


def _fill(reservation, times, segments) -> None:
    for index, (timestamp, segment) in enumerate(zip(times, segments)):
        reservation.raw[index] = (timestamp, 1, 2, 3, 4, 5, 6)
        reservation.segment_ids[index] = segment


def _series_samples() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = np.arange(6.0)
    timestamps = np.array([0.0, 60.0, 120.0, 300.0, 360.0, 420.0])
    states = np.column_stack(
        (
            7_000_000.0 + 100.0 * indices**2,
            100_000.0 * indices,
            200_000.0 + 25.0 * indices**2,
            -10.0 * indices,
            7_500.0 - 20.0 * indices,
            30.0 * indices,
        )
    )
    segments = np.array([0, 0, 0, 1, 1, 1], dtype=np.int64)
    return timestamps, states, segments


def _store_with_samples(
    times: np.ndarray,
    states: np.ndarray,
    segments: np.ndarray,
    *,
    metadata: tuple[tuple[str, object], ...] = (),
    complete: bool = True,
) -> OemDataStore:
    store = OemDataStore()
    epoch = store.begin(len(times))
    reservation = store.reserve(len(times))
    reservation.raw[:, 0] = times
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = segments
    store.commit(reservation, len(times))
    if complete:
        store.mark_complete(epoch, (), metadata)
    return store


def test_commit_publishes_zero_copy_prefix_and_preserves_snapshots() -> None:
    store = OemDataStore()
    epoch = store.begin(8)
    first = store.reserve(3)
    _fill(first, [1, 2, 5], [0, 0, 1])
    assert store.snapshot().sample_count == 0
    notice = store.commit(first, 3)
    snapshot = store.snapshot()
    assert (notice.epoch, notice.revision, notice.first_new_index, notice.sample_count) == (
        epoch, 1, 0, 3
    )
    assert (notice.start_s, notice.end_s) == (1, 5)
    np.testing.assert_array_equal(snapshot.segment_bounds, [[0, 2], [2, 3]])
    assert not snapshot.segment_bounds.flags.writeable
    assert isinstance(snapshot, StoreSnapshot)
    assert snapshot.policy_revision == 0
    assert snapshot.header == snapshot.metadata.header
    assert snapshot.meta == snapshot.metadata.meta
    assert snapshot.max_within_segment_gap_s == 1
    assert np.shares_memory(snapshot.raw, first.raw)
    assert np.shares_memory(snapshot.segment_ids, first.segment_ids)
    assert not snapshot.raw.flags.writeable
    assert not snapshot.segment_ids.flags.writeable
    assert not first.raw.flags.writeable
    with pytest.raises(ValueError):
        snapshot.raw[0, 0] = 9
    with pytest.raises(ValueError):
        snapshot.raw.setflags(write=True)
    with pytest.raises(ValueError):
        snapshot.segment_ids.setflags(write=True)

    second = store.reserve(4)
    _fill(second, [8, 10, 12], [1, 2, 2])
    store.commit(second, 3)
    extended = store.snapshot()
    np.testing.assert_array_equal(
        extended.segment_bounds, [[0, 2], [2, 4], [4, 6]]
    )
    assert extended.max_within_segment_gap_s == 3
    assert extended.revision == 2
    assert snapshot.sample_count == 3
    np.testing.assert_array_equal(snapshot.segment_bounds, [[0, 2], [2, 3]])
    np.testing.assert_array_equal(snapshot.raw[:, 0], [1, 2, 5])
    assert np.shares_memory(snapshot.raw, extended.raw)
    assert np.shares_memory(snapshot.segment_ids, extended.segment_ids)


def test_column_group_view_is_read_only_without_copying() -> None:
    source = np.arange(6, dtype=float).reshape((2, 3))
    group = ColumnGroupView(source, ("t", "x", "y"), (RowSpan(0, 2),))

    assert np.shares_memory(group.values, source)
    assert not group.values.flags.writeable
    assert source.flags.writeable
    with pytest.raises(ValueError):
        group.values[0, 0] = 9
    with pytest.raises(ValueError):
        group.values.setflags(write=True)


def test_column_group_pair_is_a_read_only_strided_view() -> None:
    source = np.arange(70_000, dtype=float).reshape((10_000, 7))
    group = ColumnGroupView(
        source,
        ("t", "x", "y", "z", "vx", "vy", "vz"),
        (RowSpan(0, len(source)),),
    )

    pair = group.pair("t", "z", slice(10, 20))
    reversed_pair = group.pair("z", "t", slice(20, 30))

    assert pair.shape == (10, 2)
    assert np.shares_memory(pair, source)
    assert not pair.flags.writeable
    np.testing.assert_array_equal(pair, source[10:20, [0, 3]])
    assert np.shares_memory(reversed_pair, source)
    assert not reversed_pair.flags.writeable
    np.testing.assert_array_equal(
        reversed_pair, source[20:30, [3, 0]]
    )


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ("unknown", "y", "must exist"),
        ("x", "x", "must be distinct"),
    ],
)
def test_column_group_pair_rejects_invalid_columns(
    first: str, second: str, message: str
) -> None:
    group = ColumnGroupView(
        np.arange(6, dtype=float).reshape((2, 3)),
        ("t", "x", "y"),
        (RowSpan(0, 2),),
    )

    with pytest.raises(ValueError, match=message):
        group.pair(first, second)


@pytest.mark.parametrize(
    ("times", "segments", "error"),
    [
        ([3, 3], [0, 0], "strictly increasing"),
        ([3, float("nan")], [0, 0], "finite"),
        ([3, 4], [1, 0], "non-decreasing"),
    ],
)
def test_invalid_reservations_do_not_publish(times, segments, error) -> None:
    store = OemDataStore()
    store.begin(4)
    reservation = store.reserve(2)
    _fill(reservation, times, segments)
    with pytest.raises(ValueError, match=error):
        store.commit(reservation, 2)
    assert store.snapshot().sample_count == 0
    assert store.snapshot().revision == 0
    store.abort(reservation)
    assert not reservation.raw.flags.writeable


def test_validation_includes_prior_tail_and_state_components() -> None:
    store = OemDataStore()
    store.begin(3)
    first = store.reserve(1)
    _fill(first, [5], [2])
    store.commit(first, 1)
    reservation = store.reserve(2)
    _fill(reservation, [6, 7], [2, 2])
    reservation.raw[0, 5] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        store.commit(reservation, 2)
    reservation.raw[0, 5] = 5
    reservation.raw[0, 0] = 5
    with pytest.raises(ValueError, match="strictly increasing"):
        store.commit(reservation, 2)
    reservation.raw[0, 0] = 6
    reservation.segment_ids[0] = 1
    with pytest.raises(ValueError, match="non-decreasing"):
        store.commit(reservation, 2)
    store.abort(reservation)
    assert store.snapshot().sample_count == 1


def test_capacity_partial_commit_and_invalid_lifecycle() -> None:
    store = OemDataStore()
    with pytest.raises(RuntimeError, match="no active epoch"):
        store.reserve(1)
    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="capacity"):
            store.begin(invalid)
    store.begin(2)
    reservation = store.reserve(8)
    assert len(reservation.raw) == 2
    with pytest.raises(RuntimeError, match="already active"):
        store.reserve(1)
    _fill(reservation, [1, 2], [0, 0])
    with pytest.raises(ValueError, match="count"):
        store.commit(reservation, 3)
    store.commit(reservation, 1)
    with pytest.raises(RuntimeError, match="stale"):
        store.commit(reservation, 1)
    next_reservation = store.reserve(2)
    assert len(next_reservation.raw) == 1
    _fill(next_reservation, [2], [0])
    store.commit(next_reservation, 1)
    with pytest.raises(OverflowError, match="capacity"):
        store.reserve(1)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"", 1),
        (b"one\n two\n", 2),
        (b"one\r\ntwo\r\n", 2),
        (b"one\rtwo\r", 2),
        (b"one\ntwo", 2),
        (b"one\r\ntwo\nthree\r", 3),
    ],
)
def test_capacity_for_file_counts_universal_physical_lines(
    tmp_path, content: bytes, expected: int
) -> None:
    source = tmp_path / "line-count.oem"
    source.write_bytes(content)
    assert OemDataStore.capacity_for_file(source) == expected


def test_capacity_for_file_excludes_covariance_rows_and_bounds_storage(
    tmp_path,
) -> None:
    covariance = "".join(
        f"EPOCH = 2026-01-01T00:{minute:02d}:00\n"
        "1\n2 3\n4 5 6\n7 8 9 10\n11 12 13 14 15\n16 17 18 19 20 21\n"
        for minute in range(20)
    )
    source = tmp_path / "covariance-heavy.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = J2000\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "COVARIANCE_START\n"
        f"{covariance}"
        "COVARIANCE_STOP\n",
        encoding="utf-8",
    )

    capacity = OemDataStore.capacity_for_file(source)
    store = OemDataStore()
    store.begin(capacity)

    assert capacity == 8
    assert len(CcsdsOem.read(source).states) <= capacity
    assert capacity < len(source.read_text(encoding="utf-8").splitlines()) // 10
    assert store._raw is not None
    assert store._segment_ids is not None
    assert store._raw.nbytes + store._segment_ids.nbytes == capacity * 64


def test_capacity_allocation_rejects_stale_loading_epoch() -> None:
    store = OemDataStore()
    epoch = store.begin_loading()
    assert store.cancel_if_epoch(epoch)
    assert not store.allocate_if_epoch(epoch, 8)
    assert store.capacity == 0
    assert store.status is LoadStatus.CANCELLED


def test_snapshot_metadata_is_immutable_after_completion() -> None:
    store = OemDataStore()
    epoch = store.begin(1)
    comments = ["initial"]
    store.mark_complete(epoch, (("COMMENT", comments),), (("OBJECT_NAME", "TEST"),))

    snapshot = store.snapshot()
    comments.append("later")

    assert snapshot.metadata.header == (("COMMENT", ("initial",)),)
    assert snapshot.metadata.meta == (("OBJECT_NAME", "TEST"),)
    assert snapshot.status is LoadStatus.COMPLETE


def test_clear_rejects_stale_reservation_and_preserves_old_snapshot() -> None:
    store = OemDataStore()
    store.begin(4)
    first = store.reserve(1)
    _fill(first, [1], [0])
    store.commit(first, 1)
    old_snapshot = store.snapshot()
    stale = store.reserve(1)
    _fill(stale, [2], [0])
    store.clear()
    assert not stale.raw.flags.writeable
    store.begin(4)
    with pytest.raises(RuntimeError, match="stale"):
        store.commit(stale, 1)
    with pytest.raises(RuntimeError, match="stale"):
        store.abort(stale)
    assert store.snapshot().sample_count == 0
    np.testing.assert_array_equal(old_snapshot.raw[:, 0], [1])
    assert store.snapshot().epoch > old_snapshot.epoch


def test_clear_if_epoch_does_not_invalidate_a_replacement() -> None:
    store = OemDataStore()
    old_epoch = store.begin(2)
    new_epoch = store.begin(3)
    assert new_epoch > old_epoch
    assert not store.clear_if_epoch(old_epoch)
    assert store.snapshot().epoch == new_epoch
    assert store.snapshot().sample_count == 0


def test_cancel_preserves_prefix_and_prevents_further_reservations() -> None:
    store = OemDataStore()
    epoch = store.begin(3)
    reservation = store.reserve(1)
    _fill(reservation, [1], [0])
    store.commit(reservation, 1)

    pending = store.reserve(1)
    _fill(pending, [2], [0])
    assert store.cancel_if_epoch(epoch)
    snapshot = store.snapshot()
    assert snapshot.status is LoadStatus.CANCELLED
    assert snapshot.sample_count == 1
    assert snapshot.failure is None
    with pytest.raises(RuntimeError, match="stale"):
        store.commit(pending, 1)
    with pytest.raises(RuntimeError, match="not loading"):
        store.reserve(1)


def test_snapshot_position_and_velocity_columns_are_raw_backed_views() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()

    assert np.shares_memory(snapshot.positions_m, snapshot.raw)
    assert np.shares_memory(snapshot.velocities_m_s, snapshot.raw)
    np.testing.assert_array_equal(snapshot.positions_m, states[:, :3])
    np.testing.assert_array_equal(snapshot.velocities_m_s, states[:, 3:])
    assert not snapshot.positions_m.flags.writeable
    assert not snapshot.velocities_m_s.flags.writeable


@pytest.mark.parametrize(
    ("method", "degree"),
    [(None, None), ("hermite", 3), ("lagrange", 3), ("chebyshev", 3)],
)
def test_state_at_matches_cursor_without_copying_sample_history(
    method: str | None, degree: int | None
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    cursor = OemCursor(
        times,
        states,
        interpolation=method,
        interpolation_degree=degree,
        segment_ids=segments,
    )
    if method is not None:
        store.set_interpolation(InterpolationPolicy(method, degree))
    snapshot = store.snapshot()

    for query_time in (0.0, 30.0, 120.0, 210.0, 300.0, 330.0, 420.0, 500.0):
        expected = cursor.lookup(query_time)
        actual = store.state_at(snapshot, query_time)

        assert actual.status is expected.status
        assert actual.segment_id == expected.segment_id
        if expected.state_m is None:
            assert actual.state_m is None
            continue
        assert actual.state_m is not None
        np.testing.assert_allclose(actual.state_m, expected.state_m, rtol=1e-12)
        assert actual.speed == pytest.approx(expected.speed)
        assert actual.altitude == pytest.approx(expected.altitude)
        assert actual.distance == pytest.approx(expected.distance)


def test_state_at_rejects_snapshot_after_interpolation_policy_change() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    old_snapshot = store.snapshot()

    store.set_interpolation(InterpolationPolicy("lagrange", 3))

    with pytest.raises(RuntimeError, match="interpolation policy has changed"):
        store.state_at(old_snapshot, 30.0)
    assert store.snapshot().policy_revision == old_snapshot.policy_revision + 1


def test_series_groups_are_lazy_chunked_views_matching_reference_computations() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    assert store._series_buffers == {}

    result = store.series(snapshot, (60.0, 360.0))
    repeated = store.series(snapshot, (60.0, 360.0), groups=("kinematics",))

    assert set(result.value) == {"kinematics", "rtn", "direction-rates"}
    assert set(store._series_buffers) == {"kinematics", "rtn", "direction-rates"}
    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert store.series_chunk_counters("kinematics").hits == 1
    for group_name in ("kinematics", "rtn", "direction-rates"):
        view = result.value[group_name].values
        assert np.shares_memory(view, store._series_buffers[group_name])
        assert not view.flags.writeable
        np.testing.assert_array_equal(view[:, 0], times[1:5])

    reference = compute_orbit_series(
        times.tolist(),
        list(states),
        TimeUnit.for_duration(float(times[-1] - times[0])),
        segments,
    )
    kinematics = result.value["kinematics"].values
    np.testing.assert_allclose(
        kinematics[:, 1],
        reference.velocity_magnitude_km_s[1:5] * 1000.0,
    )
    np.testing.assert_allclose(
        kinematics[:, 2],
        reference.geocentric_distance_km[1:5] * 1000.0,
    )
    np.testing.assert_allclose(
        kinematics[:, 3],
        reference.altitude_km[1:5] * 1000.0,
    )

    rtn = result.value["rtn"].values
    np.testing.assert_array_equal(rtn[:, 1:], store._series_buffers["rtn"][1:5, 1:])
    np.testing.assert_allclose(
        rtn[1:, 1:],
        reference.rtn_delta_km[1:4] * 1000.0,
        equal_nan=True,
    )
    assert result.value["rtn"].segment_bounds == (
        RowSpan(0, 2),
        RowSpan(3, 4),
    )

    direction = result.value["direction-rates"].values
    np.testing.assert_allclose(
        direction[:, 1],
        np.deg2rad(reference.direction_change_angle_deg[1:5]),
    )
    np.testing.assert_allclose(
        direction[:, 2],
        reference.angular_velocity_rad_s[1:5],
    )
    np.testing.assert_allclose(
        direction[:, 3:6],
        np.deg2rad(reference.euler_angles_deg[1:5]),
        atol=1e-14,
    )
    np.testing.assert_allclose(
        direction[:, 6:9],
        np.deg2rad(reference.euler_angle_rates_deg_s[1:5]),
        atol=1e-14,
    )
    assert result.coverage.covered_s == ((60.0, 120.0), (300.0, 360.0))
    assert result.coverage.complete
    assert repeated.value["kinematics"].values.shape == (4, 4)


def test_series_queries_compute_only_requested_groups_and_stride_views() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()

    query = store.series(snapshot, (0.0, 420.0), groups=("kinematics",), max_samples=3)

    assert set(query.value) == {"kinematics"}
    assert set(store._series_buffers) == {"kinematics"}
    view = query.value["kinematics"].values
    assert view.shape == (3, 4)
    assert np.shares_memory(view, store._series_buffers["kinematics"])
    assert query.value["kinematics"].segment_bounds == (
        RowSpan(0, 2),
        RowSpan(2, 3),
    )


def test_series_results_do_not_depend_on_group_request_order() -> None:
    times, states, segments = _series_samples()
    first_store = _store_with_samples(times, states, segments)
    second_store = _store_with_samples(times, states, segments)

    first = first_store.series(
        first_store.snapshot(),
        (0.0, 420.0),
        groups=("kinematics", "rtn"),
    )
    second = second_store.series(
        second_store.snapshot(),
        (0.0, 420.0),
        groups=("rtn", "kinematics"),
    )

    for group in ("kinematics", "rtn"):
        np.testing.assert_array_equal(
            first.value[group].values,
            second.value[group].values,
        )


def test_time_unit_change_does_not_recompute_or_rescale_series() -> None:
    full_chunk_size = 4096
    times = np.concatenate(
        (np.linspace(0.0, 3599.0, full_chunk_size), np.array([3600.0]))
    )
    indices = np.arange(times.size, dtype=float)
    states = np.column_stack(
        (
            7_000_000.0 + indices,
            indices**2,
            50_000.0 + 2.0 * indices,
            -indices,
            7_500.0 - 0.1 * indices,
            2.0 * indices,
        )
    )
    segments = np.zeros(times.size, dtype=np.int64)
    store = OemDataStore()
    store.begin(times.size)
    first_reservation = store.reserve(full_chunk_size)
    first_reservation.raw[:, 0] = times[:full_chunk_size]
    first_reservation.raw[:, 1:7] = states[:full_chunk_size]
    first_reservation.segment_ids[:] = segments[:full_chunk_size]
    store.commit(first_reservation, full_chunk_size)

    first_snapshot = store.snapshot()
    assert first_snapshot.time_unit is TimeUnit.MINUTES
    first = store.series(
        first_snapshot,
        (times[0], times[full_chunk_size - 1]),
        groups=("kinematics",),
    )
    original_values = first.value["kinematics"].values.copy()

    appended = store.reserve(1)
    appended.raw[:, 0] = times[full_chunk_size:]
    appended.raw[:, 1:7] = states[full_chunk_size:]
    appended.segment_ids[:] = segments[full_chunk_size:]
    store.commit(appended, 1)

    next_snapshot = store.snapshot()
    assert next_snapshot.time_unit is TimeUnit.HOURS
    repeated = store.series(
        next_snapshot,
        (times[0], times[full_chunk_size - 1]),
        groups=("kinematics",),
    )

    np.testing.assert_array_equal(repeated.value["kinematics"].values, original_values)
    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert store.series_chunk_counters("kinematics").hits == 1


def test_interpolation_policy_change_preserves_series_chunks() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    first = store.series(
        snapshot,
        (0.0, 420.0),
        groups=("kinematics",),
    )

    store.set_interpolation(InterpolationPolicy("lagrange", 3))
    next_snapshot = store.snapshot()
    repeated = store.series(
        next_snapshot,
        (0.0, 420.0),
        groups=("kinematics",),
    )

    np.testing.assert_array_equal(
        repeated.value["kinematics"].values,
        first.value["kinematics"].values,
    )
    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert store.series_chunk_counters("kinematics").hits == 1


def test_loading_append_recomputes_only_the_tentative_series_tail() -> None:
    times, states, segments = _series_samples()
    store = OemDataStore()
    epoch = store.begin(len(times))
    first = store.reserve(2)
    first.raw[:, 0] = times[:2]
    first.raw[:, 1:7] = states[:2]
    first.segment_ids[:] = segments[:2]
    store.commit(first, 2)

    first_snapshot = store.snapshot()
    partial = store.series(
        first_snapshot,
        (0.0, 420.0),
        groups=("kinematics",),
    )
    assert not partial.coverage.complete
    assert partial.coverage.covered_s == ((0.0, 60.0),)
    assert store._series_memos["kinematics"].state(
        0, epoch=epoch, policy_revision=0
    ) is ChunkState.TENTATIVE

    appended = store.reserve(1)
    appended.raw[:, 0] = times[2:3]
    appended.raw[:, 1:7] = states[2:3]
    appended.segment_ids[:] = segments[2:3]
    store.commit(appended, 1)
    next_snapshot = store.snapshot()
    query = store.series(next_snapshot, (0.0, 120.0), groups=("kinematics",))

    assert store.series_chunk_counters("kinematics").chunks_computed == 2
    assert query.value["kinematics"].values.shape == (3, 4)


def test_rtn_chunk_boundary_reads_one_previous_raw_sample() -> None:
    sample_count = 4098
    indices = np.arange(sample_count, dtype=float)
    times = indices * 60.0
    states = np.column_stack(
        (
            7_000_000.0 + indices,
            indices**2,
            50_000.0 + 2.0 * indices,
            -indices,
            7_500.0 - 0.1 * indices,
            2.0 * indices,
        )
    )
    segments = np.zeros(sample_count, dtype=np.int64)
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()

    query = store.series(
        snapshot,
        (times[4096], times[4097]),
        groups=("rtn",),
    )

    assert store._series_memos["rtn"].state(
        0, epoch=snapshot.epoch, policy_revision=0
    ) is ChunkState.ABSENT
    assert store._series_memos["rtn"].state(
        1, epoch=snapshot.epoch, policy_revision=0
    ) is ChunkState.COMPLETE
    expected = misc.transform_to_rtn(states[4096], states[4095])
    np.testing.assert_allclose(query.value["rtn"].values[0, 1:], expected)
    assert query.value["rtn"].segment_bounds == (RowSpan(0, 2),)


def test_earth_fixed_positions_are_lazy_memoized_read_only_views() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(
        times,
        states,
        segments,
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    snapshot = store.snapshot()
    assert store._earth_fixed_buffer is None

    query = store.earth_fixed_positions(snapshot, (60.0, 360.0), margin_s=0.0)
    repeated = store.earth_fixed_positions(snapshot, (60.0, 360.0))

    values = query.value.values
    assert values.shape == (4, 4)
    assert np.shares_memory(values, store._earth_fixed_buffer)
    assert not values.flags.writeable
    np.testing.assert_array_equal(values[:, 0], times[1:5])
    np.testing.assert_array_equal(values[:, 1:], states[1:5, :3])
    assert query.value.segment_bounds == (RowSpan(0, 2), RowSpan(2, 4))
    assert repeated.value.values.shape == values.shape
    assert store.earth_fixed_chunk_counters.chunks_computed == 1
    assert store.earth_fixed_chunk_counters.hits == 1


def test_clear_during_validation_cannot_publish_into_new_epoch(monkeypatch) -> None:
    store = OemDataStore()
    store.begin(2)
    stale = store.reserve(1)
    _fill(stale, [1], [0])
    entered = Event()
    release = Event()
    original_isfinite = math.isfinite

    def blocked_isfinite(value):
        if not entered.is_set():
            entered.set()
            assert release.wait(3)
        return original_isfinite(value)

    monkeypatch.setattr("ephem_toolkit.play_oem.oem_data_store.math.isfinite", blocked_isfinite)
    errors = []

    def commit() -> None:
        try:
            store.commit(stale, 1)
        except Exception as error:
            errors.append(error)

    worker = Thread(target=commit)
    worker.start()
    try:
        assert entered.wait(3)
        store.begin(2)
        current = store.reserve(1)
        _fill(current, [10], [0])
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
    monkeypatch.setattr("ephem_toolkit.play_oem.oem_data_store.math.isfinite", original_isfinite)
    store.commit(current, 1)
    np.testing.assert_array_equal(store.snapshot().raw[:, 0], [10])
