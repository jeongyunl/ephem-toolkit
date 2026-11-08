"""Tests for fixed-capacity raw OEM storage."""

import math
from threading import Event, Thread

import numpy as np
import pytest

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.oem_data_store import (
    ColumnGroupView,
    LoadStatus,
    OemDataStore,
    RowSpan,
    StoreSnapshot,
)


def _fill(reservation, times, segments) -> None:
    for index, (timestamp, segment) in enumerate(zip(times, segments)):
        reservation.raw[index] = (timestamp, 1, 2, 3, 4, 5, 6)
        reservation.segment_ids[index] = segment


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
