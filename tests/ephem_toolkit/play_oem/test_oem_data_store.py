"""Tests for fixed-capacity raw OEM storage."""

from __future__ import annotations

import gc
import math
from concurrent.futures import CancelledError
from threading import Event, Thread

import numpy as np
import pytest

from ephem_toolkit.core import misc
from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.chunk_memo import ChunkState
from ephem_toolkit.play_oem.cursor import StoreCursor
from ephem_toolkit.play_oem.ground_footprints import compute_ground_footprints
from ephem_toolkit.play_oem.ground_stations import GroundStation, station_metrics

import ephem_toolkit.play_oem.oem_data_store as oem_data_store
import ephem_toolkit.play_oem.ground_track as ground_track
from ephem_toolkit.play_oem.oem_data_store import (
    ColumnGroupView,
    InterpolationPolicy,
    LoadStatus,
    OemDataStore,
    QueryRequest,
    RangeHint,
    RowSpan,
    StoreSnapshot,
)
from ephem_toolkit.play_oem.series import (
    SERIES_GROUPS,
    compute_orbit_series,
    compute_series_chunk,
)
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
    derived_memory_budget_bytes: int = 256 * 1024 * 1024,
) -> OemDataStore:
    store = OemDataStore(derived_memory_budget_bytes)
    epoch = store.begin(len(times))
    reservation = store.reserve(len(times))
    reservation.raw[:, 0] = times
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = segments
    store.commit(reservation, len(times))
    if complete:
        store.mark_complete(epoch, (), metadata)
    return store


def _one_group(query, name: str) -> ColumnGroupView:
    views = query.value[name]
    assert len(views) == 1
    return views[0]


def test_earth_centered_queries_preserve_incomplete_metadata_results() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments, complete=False)
    snapshot = store.snapshot()
    station = GroundStation("station", "Test Station", 35.0, -117.0, 100.0)

    assert store.station_metrics_at(snapshot, station, times[0]) is None
    assert store.footprints(snapshot, times[0], 10.0) is None

    earth_fixed = store.earth_fixed_positions(
        snapshot, (times[0], times[-1]), wait=True
    )
    ground_track_result = store.ground_track(
        snapshot, (times[0], times[-1]), wait=True
    )
    station_access_result = store.station_access(
        snapshot, station, (times[0], times[-1]), wait=True
    )

    for query in (earth_fixed, ground_track_result, station_access_result):
        assert query.epoch == snapshot.epoch
        assert query.revision == snapshot.revision
        assert query.policy_revision == snapshot.policy_revision
        assert query.coverage.covered_s == ()
        assert not query.coverage.complete
    assert earth_fixed.value == ()
    assert ground_track_result.value == ()
    assert station_access_result.value.profiles == ()
    assert station_access_result.value.intervals == ()
    assert station_access_result.value.limitation is None


@pytest.mark.parametrize(
    ("metadata", "error_message"),
    [
        ((), "requires CENTER_NAME and REF_FRAME metadata"),
        (
            (("CENTER_NAME", "MARS"), ("REF_FRAME", "ITRF")),
            "requires an Earth-centered OEM; found 'MARS'",
        ),
    ],
)
def test_earth_centered_queries_preserve_metadata_errors(
    metadata: tuple[tuple[str, object], ...], error_message: str
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(
        times,
        states,
        segments,
        metadata=metadata,
    )
    snapshot = store.snapshot()
    station = GroundStation("station", "Test Station", 35.0, -117.0, 100.0)
    operations = (
        (
            "Station metrics",
            lambda: store.station_metrics_at(snapshot, station, times[0]),
        ),
        ("Footprints", lambda: store.footprints(snapshot, times[0], 10.0)),
        (
            "Earth-fixed positions",
            lambda: store.earth_fixed_positions(
                snapshot, (times[0], times[-1]), wait=True
            ),
        ),
        (
            "Ground Track",
            lambda: store.ground_track(
                snapshot, (times[0], times[-1]), wait=True
            ),
        ),
        (
            "Station access",
            lambda: store.station_access(
                snapshot, station, (times[0], times[-1]), wait=True
            ),
        ),
    )

    for purpose, operation in operations:
        with pytest.raises(oem_data_store.GroundTrackPreparationError) as error:
            operation()
        assert str(error.value) == f"{purpose} {error_message}"


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


def test_capacity_for_file_scans_ascii_markers_across_chunk_boundaries(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "chunk-boundaries.oem"
    source.write_bytes(
        b"before\r\n"
        b"COVARIANCE_START\r\n"
        b"covariance row\r\n"
        b"COVARIANCE_STOP\r\n"
        b"after"
    )
    monkeypatch.setattr(oem_data_store, "_CAPACITY_SCAN_CHUNK_SIZE", 7)

    assert OemDataStore.capacity_for_file(source) == 2


def test_capacity_for_file_requires_complete_covariance_marker_lines(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "marker-lines.oem"
    source.write_bytes(
        b"COVARIANCE_NOT_A_MARKER\n"
        b"before\n"
        b"COVARIANCE_START\n"
        b"covariance row\n"
        b"COVARIANCE_STOP\n"
        b"COVARIANCE_START trailing\n"
        b"after"
    )
    monkeypatch.setattr(oem_data_store, "_CAPACITY_SCAN_CHUNK_SIZE", 7)

    assert OemDataStore.capacity_for_file(source) == 4


def test_capacity_for_file_checks_ascii_line_length_across_crlf_chunks(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "ascii-line-length.oem"
    limit = oem_data_store.ODM_MAX_LINE_LENGTH
    prefix_length = (5 - limit) % 7
    source.write_bytes(
        b"p" * prefix_length + b"\n" + b"x" * limit + b"\r\n"
    )
    monkeypatch.setattr(oem_data_store, "_CAPACITY_SCAN_CHUNK_SIZE", 7)

    assert OemDataStore.capacity_for_file(source) == 2

    source.write_bytes(b"x" * (limit + 1))
    with pytest.raises(ValueError, match="character line limit"):
        OemDataStore.capacity_for_file(source)


def test_capacity_for_file_preserves_strict_utf8_and_cancellation(
    tmp_path,
) -> None:
    source = tmp_path / "invalid-utf8.oem"
    source.write_bytes(b"header\n\xff")
    with pytest.raises(UnicodeDecodeError):
        OemDataStore.capacity_for_file(source)

    cancel_event = Event()
    cancel_event.set()
    with pytest.raises(InterruptedError, match="capacity scan cancelled"):
        OemDataStore.capacity_for_file(source, cancel_event=cancel_event)


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


def test_capacity_for_file_only_treats_stripped_covariance_markers_as_boundaries(
    tmp_path,
) -> None:
    source = tmp_path / "marker-boundaries.oem"
    source.write_text(
        "header\n"
        "prefix COVARIANCE_START suffix\n"
        "\u2003COVARIANCE_START\u2003\n"
        "covariance row\n"
        "prefix COVARIANCE_STOP suffix\n"
        "\u2003COVARIANCE_STOP\u2003\n"
        "tail\n",
        encoding="utf-8",
    )

    assert OemDataStore.capacity_for_file(source) == 3


def test_capacity_for_file_preserves_unicode_line_length_limit(tmp_path) -> None:
    source = tmp_path / "unicode-line-length.oem"
    source.write_text(
        "é" * oem_data_store.ODM_MAX_LINE_LENGTH,
        encoding="utf-8",
    )
    assert OemDataStore.capacity_for_file(source) == 1

    source.write_text(
        "é" * (oem_data_store.ODM_MAX_LINE_LENGTH + 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="character line limit"):
        OemDataStore.capacity_for_file(source)


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


def test_store_sample_times_share_raw_timestamp_column_and_follow_commits() -> None:
    store = OemDataStore()
    store.begin(3)
    sample_times = store.sample_times
    assert len(sample_times) == 0

    first = store.reserve(2)
    _fill(first, [10.0, 20.0], [0, 0])
    store.commit(first, 2)

    snapshot = store.snapshot()
    assert len(sample_times) == 2
    assert np.shares_memory(sample_times.values, snapshot.raw)
    np.testing.assert_array_equal(sample_times.values, [10.0, 20.0])

    appended = store.reserve(1)
    _fill(appended, [30.0], [0])
    store.commit(appended, 1)
    assert len(sample_times) == 3
    np.testing.assert_array_equal(sample_times.values, [10.0, 20.0, 30.0])


@pytest.mark.parametrize(
    ("method", "degree"),
    [(None, None), ("hermite", 3), ("lagrange", 3), ("chebyshev", 3)],
)
def test_store_cursor_queries_do_not_materialize_sample_history(
    method: str | None, degree: int | None
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    if method is not None:
        store.set_interpolation(InterpolationPolicy(method, degree))
    snapshot = store.snapshot()
    cursor = StoreCursor(store, snapshot)
    assert store._series_buffers == {}
    assert store._earth_fixed_buffer is None

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
        assert store._series_buffers == {}
        assert store._earth_fixed_buffer is None


def test_point_queries_reuse_raw_state_without_materializing_history_tiers() -> None:
    times, states, segments = _series_samples()
    metadata = (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF93"))
    store = _store_with_samples(times, states, segments, metadata=metadata)
    snapshot = store.snapshot()
    station = GroundStation("station", "Test Station", 35.0, -117.0, 100.0)

    metrics = store.station_metrics_at(snapshot, station, 0.0)
    expected_metrics = station_metrics(station, states[0], "ITRF93", 0.0)
    assert metrics == expected_metrics
    assert store.station_metrics_at(snapshot, station, 210.0) is None
    assert store.station_metrics_at(snapshot, station, 500.0) is None

    footprints = store.footprints(snapshot, 0.0, 10)
    expected_footprints = compute_ground_footprints(states[0, :3], 10)
    assert footprints is not None
    np.testing.assert_allclose(
        footprints.horizon.latitude_rad,
        expected_footprints.horizon.latitude_rad,
    )
    np.testing.assert_allclose(
        footprints.horizon.longitude_rad,
        expected_footprints.horizon.longitude_rad,
    )
    assert store.footprints(snapshot, 0.0, 10) is footprints
    assert store.footprints(snapshot, 210.0, 10) is None
    assert store._earth_fixed_buffer is None


def test_ground_track_query_reuses_earth_fixed_positions_and_splits_map_seams() -> None:
    times = np.array([0.0, 10.0, 20.0, 30.0])
    longitudes_rad = np.deg2rad([170.0, -170.0, -160.0, 170.0])
    radius_m = 6_378_137.0 + 400_000.0
    positions = np.column_stack(
        (
            radius_m * np.cos(longitudes_rad),
            radius_m * np.sin(longitudes_rad),
            np.zeros(times.size),
        )
    )
    states = np.column_stack((positions, np.zeros_like(positions)))
    segments = np.array([0, 0, 0, 1], dtype=np.int64)
    metadata = (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    store = _store_with_samples(times, states, segments, metadata=metadata)
    snapshot = store.snapshot()

    across_zero = store.ground_track(snapshot, (0.0, 30.0), wait=True)

    assert across_zero.coverage.complete
    assert [len(group.values) for group in across_zero.value] == [2, 3, 1]
    np.testing.assert_allclose(
        np.rad2deg(across_zero.value[0].values[:, 1]), [170.0, 180.0], atol=1e-8
    )
    np.testing.assert_allclose(
        np.rad2deg(across_zero.value[1].values[:, 1]),
        [-180.0, -170.0, -160.0],
        atol=1e-8,
    )
    assert across_zero.value[0].values[-1, 0] == pytest.approx(5.0)
    assert across_zero.value[1].values[0, 0] == pytest.approx(5.0)
    assert all(
        group.columns == ("t", "longitude", "latitude")
        for group in across_zero.value
    )
    assert all(not group.values.flags.writeable for group in across_zero.value)
    assert store._earth_fixed_buffer is not None
    assert store.ground_track(snapshot, (0.0, 30.0), wait=True) is across_zero

    around_180 = store.ground_track(
        snapshot, (0.0, 30.0), center_longitude_deg=180.0, wait=True
    )
    assert len(around_180.value) == 2
    np.testing.assert_allclose(
        np.rad2deg(around_180.value[0].values[:, 1]), [-10.0, 10.0, 20.0], atol=1e-8
    )


def test_ground_track_cache_survives_interpolation_policy_change() -> None:
    times = np.array([0.0, 10.0, 20.0])
    longitudes_rad = np.deg2rad([10.0, 20.0, 30.0])
    radius_m = 6_378_137.0 + 400_000.0
    positions = np.column_stack(
        (
            radius_m * np.cos(longitudes_rad),
            radius_m * np.sin(longitudes_rad),
            np.zeros(times.size),
        )
    )
    states = np.column_stack((positions, np.zeros_like(positions)))
    metadata = (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    store = _store_with_samples(
        times,
        states,
        np.zeros(times.size, dtype=np.int64),
        metadata=metadata,
    )
    first_snapshot = store.snapshot()
    first = store.ground_track(first_snapshot, (0.0, 20.0), wait=True)

    store.set_interpolation(InterpolationPolicy("lagrange", 3))
    next_snapshot = store.snapshot()
    repeated = store.ground_track(next_snapshot, (0.0, 20.0), wait=True)

    assert repeated.policy_revision == next_snapshot.policy_revision
    assert repeated.value is first.value
    assert len(store._ground_track_cache) == 1


def test_ground_track_query_is_range_limited_and_prefetchable() -> None:
    times = np.array([0.0, 10.0, 20.0, 30.0])
    longitudes_rad = np.deg2rad([10.0, 20.0, 30.0, 40.0])
    radius_m = 6_378_137.0 + 400_000.0
    positions = np.column_stack(
        (
            radius_m * np.cos(longitudes_rad),
            radius_m * np.sin(longitudes_rad),
            np.zeros(times.size),
        )
    )
    states = np.column_stack((positions, np.zeros_like(positions)))
    metadata = (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    store = _store_with_samples(
        times, states, np.zeros(times.size, dtype=np.int64), metadata=metadata
    )
    snapshot = store.snapshot()

    pending = store.ground_track(snapshot, (10.0, 20.0), margin_s=10.0)
    assert pending.value == ()
    assert not pending.coverage.complete
    future = store.prefetch(
        snapshot,
        QueryRequest(
            "ground-track",
            (10.0, 20.0),
            margin_s=10.0,
            center_longitude_deg=360.0,
        ),
    )
    future.result(timeout=5)

    ready = store.ground_track(snapshot, (10.0, 20.0), margin_s=10.0)
    assert ready.coverage.complete
    assert len(ready.value) == 1
    np.testing.assert_array_equal(ready.value[0].values[:, 0], times)


def test_ground_track_result_cache_respects_derived_memory_budget() -> None:
    times = np.array([0.0, 10.0, 20.0])
    longitudes_rad = np.deg2rad([10.0, 20.0, 30.0])
    radius_m = 6_378_137.0 + 400_000.0
    positions = np.column_stack(
        (
            radius_m * np.cos(longitudes_rad),
            radius_m * np.sin(longitudes_rad),
            np.zeros(times.size),
        )
    )
    states = np.column_stack((positions, np.zeros_like(positions)))
    metadata = (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    store = _store_with_samples(
        times,
        states,
        np.zeros(times.size, dtype=np.int64),
        metadata=metadata,
        derived_memory_budget_bytes=1,
    )

    result = store.ground_track(store.snapshot(), (0.0, 20.0), wait=True)

    assert result.coverage.complete
    assert len(result.value) == 1
    assert store._ground_track_cache == {}


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

    result = store.series(snapshot, (60.0, 360.0), wait=True)
    repeated = store.series(
        snapshot, (60.0, 360.0), groups=("kinematics",), wait=True
    )

    expected_groups: set[oem_data_store.SeriesGroupName] = {
        "kinematics",
        "rtn",
        "direction-rates",
        "distance-delta",
    }
    assert set(result.value) == expected_groups
    assert set(store._series_buffers) == expected_groups
    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert store.series_chunk_counters("kinematics").hits == 1
    for group_name in expected_groups:
        view = _one_group(result, group_name).values
        assert np.shares_memory(view, store._series_buffers[group_name])
        assert not view.flags.writeable
        np.testing.assert_array_equal(view[:, 0], times[1:5])

    reference = compute_orbit_series(
        times.tolist(),
        list(states),
        TimeUnit.for_duration(float(times[-1] - times[0])),
        segments,
    )
    kinematics = _one_group(result, "kinematics").values
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

    distance_delta = _one_group(result, "distance-delta")
    expected_distance_delta = np.diff(reference.geocentric_distance_km) * 1000.0
    np.testing.assert_allclose(
        distance_delta.values[:2, 1],
        expected_distance_delta[:2],
    )
    np.testing.assert_allclose(
        distance_delta.values[3:4, 1],
        expected_distance_delta[3:4],
    )
    assert distance_delta.segment_bounds == (
        RowSpan(0, 2),
        RowSpan(3, 4),
    )

    rtn = _one_group(result, "rtn").values
    np.testing.assert_array_equal(rtn[:, 1:], store._series_buffers["rtn"][1:5, 1:])
    np.testing.assert_allclose(
        rtn[1:, 1:],
        reference.rtn_delta_km[1:4] * 1000.0,
        equal_nan=True,
    )
    assert _one_group(result, "rtn").segment_bounds == (
        RowSpan(0, 2),
        RowSpan(3, 4),
    )

    direction = _one_group(result, "direction-rates").values
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
    assert _one_group(repeated, "kinematics").values.shape == (4, 4)


def test_compute_series_chunk_matches_batch_reference_without_store_state() -> None:
    times, states, segments = _series_samples()
    raw = np.column_stack((times, states))
    reference = compute_orbit_series(
        times.tolist(),
        list(states),
        TimeUnit.for_duration(float(times[-1] - times[0])),
        segments,
    )
    expected: dict[str, np.ndarray] = {
        "kinematics": np.column_stack(
            (
                times,
                reference.velocity_magnitude_km_s * 1000.0,
                reference.geocentric_distance_km * 1000.0,
                reference.altitude_km * 1000.0,
            )
        ),
    }

    rtn = np.full((len(times), 7), np.nan)
    rtn[:, 0] = times
    rtn[1:, 1:] = reference.rtn_delta_km * 1000.0
    expected["rtn"] = rtn
    expected["direction-rates"] = np.column_stack(
        (
            times,
            np.deg2rad(reference.direction_change_angle_deg),
            reference.angular_velocity_rad_s,
            np.deg2rad(reference.euler_angles_deg),
            np.deg2rad(reference.euler_angle_rates_deg_s),
        )
    )
    distance_delta = np.zeros(len(times))
    same_segment = segments[1:] == segments[:-1]
    distance_delta[1:][same_segment] = np.diff(
        reference.geocentric_distance_km
    )[same_segment] * 1000.0
    expected["distance-delta"] = np.column_stack((times, distance_delta))

    for group in SERIES_GROUPS:
        computed = compute_series_chunk(raw, segments, group, 0, len(times))
        np.testing.assert_allclose(
            computed, expected[group], atol=1e-14, equal_nan=True
        )
        sliced = compute_series_chunk(raw, segments, group, 1, len(times) - 1)
        np.testing.assert_allclose(
            sliced, expected[group][1:-1], atol=1e-14, equal_nan=True
        )


def test_series_computes_only_rows_inside_requested_ranges(monkeypatch) -> None:
    sample_count = 6000
    indices = np.arange(sample_count, dtype=float)
    times = indices
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
    store = _store_with_samples(
        times, states, np.zeros(sample_count, dtype=np.int64)
    )
    snapshot = store.snapshot()
    computed_spans = []
    original_write = oem_data_store._write_series_chunk

    def record_write(snapshot, group, start, stop, output) -> None:
        computed_spans.append((start, stop))
        original_write(snapshot, group, start, stop, output)

    monkeypatch.setattr(oem_data_store, "_write_series_chunk", record_write)

    first = store.series(
        snapshot, (4500.0, 4501.0), groups=("kinematics",), wait=True
    )
    repeated = store.series(
        snapshot, (4500.0, 4501.0), groups=("kinematics",), wait=True
    )
    second = store.series(
        snapshot, (5000.0, 5001.0), groups=("kinematics",), wait=True
    )

    assert computed_spans == [(4500, 4502), (5000, 5002)]
    np.testing.assert_array_equal(
        _one_group(first, "kinematics").values[:, 0], [4500.0, 4501.0]
    )
    np.testing.assert_array_equal(
        _one_group(repeated, "kinematics").values[:, 0], [4500.0, 4501.0]
    )
    np.testing.assert_array_equal(
        _one_group(second, "kinematics").values[:, 0], [5000.0, 5001.0]
    )
    np.testing.assert_array_equal(
        np.flatnonzero(store._series_ready["kinematics"]),
        [4500, 4501, 5000, 5001],
    )


def test_series_queries_compute_only_requested_groups_and_stride_views() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()

    query = store.series(
        snapshot,
        (0.0, 420.0),
        groups=("kinematics",),
        max_samples=3,
        wait=True,
    )

    assert set(query.value) == {"kinematics"}
    assert set(store._series_buffers) == {"kinematics"}
    view = _one_group(query, "kinematics").values
    assert view.shape == (3, 4)
    assert np.shares_memory(view, store._series_buffers["kinematics"])
    assert _one_group(query, "kinematics").segment_bounds == (
        RowSpan(0, 2),
        RowSpan(2, 3),
    )


def test_distance_delta_series_is_lazy_and_segment_aware() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()

    assert store.series_chunk_counters("distance-delta").chunks_computed == 0
    query = store.series(
        snapshot,
        (60.0, 360.0),
        groups=("distance-delta",),
        wait=True,
    )

    assert set(query.value) == {"distance-delta"}
    assert set(store._series_buffers) == {"distance-delta"}
    group = _one_group(query, "distance-delta")
    assert group.columns == ("t", "delta_distance_m")
    assert group.segment_bounds == (RowSpan(0, 2), RowSpan(3, 4))
    expected_distance = np.linalg.norm(states[:, :3], axis=1)
    expected_delta = np.diff(expected_distance)
    np.testing.assert_allclose(
        group.values[:2, 1],
        expected_delta[:2],
    )
    np.testing.assert_allclose(group.values[3:4, 1], expected_delta[3:4])
    assert query.coverage.covered_s == ((60.0, 120.0), (300.0, 360.0))
    assert store.series_chunk_counters("distance-delta").chunks_computed == 1


def test_distance_delta_recomputes_tentative_tail_after_append() -> None:
    times, states, segments = _series_samples()
    store = OemDataStore()
    epoch = store.begin(len(times))
    first = store.reserve(3)
    first.raw[:, 0] = times[:3]
    first.raw[:, 1:7] = states[:3]
    first.segment_ids[:] = segments[:3]
    store.commit(first, 3)
    first_snapshot = store.snapshot()
    store.series(
        first_snapshot,
        (times[0], times[2]),
        groups=("distance-delta",),
        wait=True,
    )

    tail = store.reserve(3)
    tail.raw[:, 0] = times[3:]
    tail.raw[:, 1:7] = states[3:]
    tail.segment_ids[:] = segments[3:]
    store.commit(tail, 3)
    store.mark_complete(epoch, (), ())

    snapshot = store.snapshot()
    query = store.series(
        snapshot,
        (times[0], times[-1]),
        groups=("distance-delta",),
        wait=True,
    )
    group = _one_group(query, "distance-delta")
    expected_distance = np.linalg.norm(states[:, :3], axis=1)
    expected_delta = np.diff(expected_distance)

    assert group.segment_bounds == (RowSpan(1, 3), RowSpan(4, 6))
    np.testing.assert_allclose(group.values[1:3, 1], expected_delta[:2])
    np.testing.assert_allclose(group.values[4:6, 1], expected_delta[3:5])
    assert query.coverage.complete


def test_series_results_do_not_depend_on_group_request_order() -> None:
    times, states, segments = _series_samples()
    first_store = _store_with_samples(times, states, segments)
    second_store = _store_with_samples(times, states, segments)

    first = first_store.series(
        first_store.snapshot(),
        (0.0, 420.0),
        groups=("kinematics", "rtn"),
        wait=True,
    )
    second = second_store.series(
        second_store.snapshot(),
        (0.0, 420.0),
        groups=("rtn", "kinematics"),
        wait=True,
    )

    for group in ("kinematics", "rtn"):
        np.testing.assert_array_equal(
            _one_group(first, group).values,
            _one_group(second, group).values,
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
        wait=True,
    )
    original_values = _one_group(first, "kinematics").values.copy()

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
        wait=True,
    )

    np.testing.assert_array_equal(
        _one_group(repeated, "kinematics").values, original_values
    )
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
        wait=True,
    )

    store.set_interpolation(InterpolationPolicy("lagrange", 3))
    next_snapshot = store.snapshot()
    repeated = store.series(
        next_snapshot,
        (0.0, 420.0),
        groups=("kinematics",),
        wait=True,
    )

    np.testing.assert_array_equal(
        _one_group(repeated, "kinematics").values,
        _one_group(first, "kinematics").values,
    )
    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert store.series_chunk_counters("kinematics").hits == 1


def test_prefetch_deduplicates_identical_requests_and_publishes_chunk_notice(
    monkeypatch,
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    request = QueryRequest(
        "series",
        (0.0, 420.0),
        series_groups=("kinematics",),
    )
    entered = Event()
    release = Event()
    notices = []
    original_write = oem_data_store._write_series_chunk

    def blocked_write(*args, **kwargs) -> None:
        entered.set()
        assert release.wait(3)
        original_write(*args, **kwargs)

    monkeypatch.setattr(
        "ephem_toolkit.play_oem.oem_data_store._write_series_chunk",
        blocked_write,
    )
    store.subscribe(notices.append)
    first = store.prefetch(snapshot, request)
    try:
        assert entered.wait(3)
        second = store.prefetch(snapshot, request)
        assert second is first
    finally:
        release.set()
        try:
            first.result(timeout=3)
        finally:
            store.close()

    assert store.series_chunk_counters("kinematics").chunks_computed == 1
    assert len(notices) == 1
    assert notices[0].tier == "series"
    assert notices[0].group == "kinematics"
    assert (notices[0].first_row, notices[0].stop_row) == (0, len(times))


def test_prefetch_keys_policy_revision_only_for_station_access(monkeypatch) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    monkeypatch.setattr(store, "_start_scheduler_drain_locked", lambda: None)
    snapshot = store.snapshot()
    ground_track_request = QueryRequest("ground-track", (0.0, 420.0))
    station = GroundStation("station", "Test Station", 35.0, -117.0, 100.0)
    station_request = QueryRequest(
        "station-access",
        (0.0, 420.0),
        station=station,
    )

    ground_track_first = store.prefetch(snapshot, ground_track_request)
    station_first = store.prefetch(snapshot, station_request)
    store.set_interpolation(InterpolationPolicy("lagrange", 3))
    next_snapshot = store.snapshot()

    ground_track_next = store.prefetch(next_snapshot, ground_track_request)
    station_next = store.prefetch(next_snapshot, station_request)
    store.close()

    assert ground_track_next is ground_track_first
    assert station_next is not station_first


def test_range_hint_prioritizes_active_tier_ranges() -> None:
    store = OemDataStore()
    unsubscribe = store.subscribe_tier("series")
    store.set_range_hint(
        RangeHint(
            plot=(100.0, 200.0),
            playback=(0.0, 1000.0),
            now_s=150.0,
        )
    )

    def priority(bounds: tuple[float, float]) -> int:
        return store._priority_for_request(
            QueryRequest("series", bounds),
            store._range_hint,
        )

    assert priority((120.0, 180.0)) == 1
    assert priority((0.0, 50.0)) == 2
    assert priority((500.0, 600.0)) == 3
    assert priority((1100.0, 1200.0)) == 4
    unsubscribe()
    store.close()


@pytest.mark.parametrize(
    ("tier", "margin", "expected"),
    [
        ("series", 20.0, (100.0, 200.0)),
        ("earth-fixed", 20.0, (80.0, 220.0)),
        ("ground-track", 20.0, (80.0, 220.0)),
        (
            "station-access",
            20.0,
            (
                100.0
                - max(
                    oem_data_store.ACCESS_WINDOW_MIN_MARGIN_S,
                    oem_data_store.ACCESS_WINDOW_MARGIN_FRACTION * 100.0,
                ),
                200.0
                + max(
                    oem_data_store.ACCESS_WINDOW_MIN_MARGIN_S,
                    oem_data_store.ACCESS_WINDOW_MARGIN_FRACTION * 100.0,
                ),
            ),
        ),
    ],
)
def test_request_bounds_include_each_tiers_support_margin(
    tier: oem_data_store.TierName,
    margin: float,
    expected: tuple[float, float],
) -> None:
    request = QueryRequest(tier, (100.0, 200.0), margin_s=margin)

    assert oem_data_store._expanded_request_bounds(request) == expected


def test_scheduler_priority_and_drag_size_use_expanded_request_bounds() -> None:
    times = np.array([0.0, 50.0, 100.0, 150.0, 200.0, 250.0])
    states = np.zeros((times.size, 6))
    segments = np.zeros(times.size, dtype=np.int64)
    store = _store_with_samples(times, states, segments)
    unsubscribe = store.subscribe_tier("earth-fixed")
    hint = RangeHint(
        plot=(100.0, 200.0),
        playback=(500.0, 600.0),
        now_s=150.0,
        dragging=True,
    )
    store.set_range_hint(hint)
    request = QueryRequest(
        "earth-fixed",
        (0.0, 10.0),
        margin_s=95.0,
    )

    assert store._priority_for_request(request, hint) == 1
    snapshot = store.snapshot()
    work = oem_data_store._ScheduledWork(
        priority=1,
        sequence=0,
        key=(snapshot.epoch, snapshot.revision, 0, request),
        snapshot=snapshot,
        request=request,
        future=oem_data_store._PrefetchFuture(),
        generation=0,
    )
    assert store._request_rows(work) == 3

    unsubscribe()
    store.close()


def test_nonblocking_series_query_does_not_report_uncomputed_data_complete() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    request = QueryRequest(
        "series",
        (times[0], times[-1]),
        series_groups=("kinematics",),
    )
    store.set_range_hint(
        RangeHint(
            plot=(10_000.0, 20_000.0),
            playback=(10_000.0, 20_000.0),
            now_s=15_000.0,
            dragging=True,
        )
    )

    partial = store.series(
        snapshot,
        request.bounds_s,
        groups=request.series_groups,
    )

    assert partial.value["kinematics"] == ()
    assert partial.coverage.covered_s == ()
    assert not partial.coverage.complete

    store.set_range_hint(
        RangeHint(
            plot=request.bounds_s,
            playback=request.bounds_s,
            now_s=times[0],
        )
    )
    store.prefetch(snapshot, request).result(timeout=3)
    completed = store.series(
        snapshot,
        request.bounds_s,
        groups=request.series_groups,
    )
    assert len(completed.value["kinematics"]) == 1
    assert completed.coverage.complete
    store.close()


def test_range_hint_cancels_stale_work_between_chunks(monkeypatch) -> None:
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
    store = _store_with_samples(
        times,
        states,
        np.zeros(sample_count, dtype=np.int64),
    )
    snapshot = store.snapshot()
    entered = Event()
    release = Event()
    original_write = oem_data_store._write_series_chunk

    def blocked_write(*args, **kwargs) -> None:
        entered.set()
        assert release.wait(3)
        original_write(*args, **kwargs)

    monkeypatch.setattr(
        "ephem_toolkit.play_oem.oem_data_store._write_series_chunk",
        blocked_write,
    )
    future = store.prefetch(
        snapshot,
        QueryRequest(
            "series",
            (times[0], times[-1]),
            series_groups=("kinematics",),
        ),
    )
    try:
        assert entered.wait(3)
        store.set_range_hint(
            RangeHint(
                plot=(300_000.0, 360_000.0),
                playback=(300_000.0, 360_000.0),
                now_s=330_000.0,
            )
        )
    finally:
        release.set()

    try:
        with pytest.raises(CancelledError):
            future.result(timeout=3)
    finally:
        store.close()
    assert store._series_memos["kinematics"].state(
        0,
        epoch=snapshot.epoch,
        policy_revision=0,
    ) is ChunkState.ABSENT
    store.close()


def test_clear_cancels_active_prefetch_without_publishing_old_epoch(
    monkeypatch,
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    entered = Event()
    release = Event()
    original_write = oem_data_store._write_series_chunk

    def blocked_write(*args, **kwargs) -> None:
        entered.set()
        assert release.wait(3)
        original_write(*args, **kwargs)

    monkeypatch.setattr(
        "ephem_toolkit.play_oem.oem_data_store._write_series_chunk",
        blocked_write,
    )
    future = store.prefetch(
        snapshot,
        QueryRequest(
            "series",
            (times[0], times[-1]),
            series_groups=("kinematics",),
        ),
    )
    memo = None
    try:
        assert entered.wait(3)
        memo = store._series_memos["kinematics"]
        store.clear()
        assert future.cancel_event.is_set()
    finally:
        release.set()

    with pytest.raises(CancelledError):
        future.result(timeout=3)
    assert store.epoch > snapshot.epoch
    assert memo is not None
    assert memo.state(
        0,
        epoch=snapshot.epoch,
        policy_revision=0,
    ) is ChunkState.ABSENT
    store.close()


def test_close_cancels_active_prefetch_and_waits_for_worker(
    monkeypatch,
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    snapshot = store.snapshot()
    entered = Event()
    release = Event()
    close_finished = Event()
    close_errors: list[Exception] = []
    original_write = oem_data_store._write_series_chunk

    def blocked_write(*args, **kwargs) -> None:
        entered.set()
        assert release.wait(3)
        original_write(*args, **kwargs)

    def close_store() -> None:
        try:
            store.close()
        except Exception as error:
            close_errors.append(error)
        finally:
            close_finished.set()

    closer = Thread(target=close_store)
    monkeypatch.setattr(
        "ephem_toolkit.play_oem.oem_data_store._write_series_chunk",
        blocked_write,
    )
    future = store.prefetch(
        snapshot,
        QueryRequest(
            "series",
            (times[0], times[-1]),
            series_groups=("kinematics",),
        ),
    )
    try:
        assert entered.wait(3)
        closer = Thread(target=close_store)
        closer.start()
        assert future.cancel_event.wait(3)
        assert not close_finished.is_set()
    finally:
        release.set()
        if closer.ident is not None:
            closer.join(3)

    assert closer.ident is not None
    assert not closer.is_alive()
    assert close_finished.is_set()
    assert close_errors == []
    with pytest.raises(CancelledError):
        future.result(timeout=3)


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
        wait=True,
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
    query = store.series(
        next_snapshot,
        (0.0, 120.0),
        groups=("kinematics",),
        wait=True,
    )

    assert store.series_chunk_counters("kinematics").chunks_computed == 2
    assert _one_group(query, "kinematics").values.shape == (3, 4)


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
        wait=True,
    )

    assert store._series_memos["rtn"].state(
        0, epoch=snapshot.epoch, policy_revision=0
    ) is ChunkState.ABSENT
    assert store._series_memos["rtn"].state(
        1, epoch=snapshot.epoch, policy_revision=0
    ) is ChunkState.COMPLETE
    expected = misc.transform_to_rtn(states[4096], states[4095])
    np.testing.assert_allclose(_one_group(query, "rtn").values[0, 1:], expected)
    assert _one_group(query, "rtn").segment_bounds == (RowSpan(0, 2),)


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

    query = store.earth_fixed_positions(
        snapshot, (60.0, 360.0), margin_s=0.0, wait=True
    )
    repeated = store.earth_fixed_positions(snapshot, (60.0, 360.0), wait=True)

    assert len(query.value) == 1
    values = query.value[0].values
    assert values.shape == (4, 4)
    assert np.shares_memory(values, store._earth_fixed_buffer)
    assert not values.flags.writeable
    np.testing.assert_array_equal(values[:, 0], times[1:5])
    np.testing.assert_array_equal(values[:, 1:], states[1:5, :3])
    assert query.value[0].segment_bounds == (RowSpan(0, 2), RowSpan(2, 4))
    assert repeated.value[0].values.shape == values.shape
    assert store.earth_fixed_chunk_counters.chunks_computed == 1
    assert store.earth_fixed_chunk_counters.hits == 1


@pytest.mark.parametrize(
    ("source_frame", "conversion_frame"),
    [(" gcrf ", "J2000"), ("TEME", "TEME"), ("itrf93", None)],
)
def test_earth_fixed_chunk_normalizes_frame_once(
    monkeypatch, source_frame: str, conversion_frame: str | None
) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(
        times,
        states,
        segments,
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", source_frame)),
    )
    normalized_names: list[str] = []
    converted_epochs: list[float] = []
    normalize = ground_track.normalize_frame_name

    def record_normalization(frame_name: str) -> str:
        normalized_names.append(frame_name)
        return normalize(frame_name)

    def convert(frame_name: str, epoch: float, state: np.ndarray) -> np.ndarray:
        assert frame_name == conversion_frame
        converted_epochs.append(epoch)
        result = state.copy()
        result[:3] += epoch
        return result

    monkeypatch.setattr(ground_track, "normalize_frame_name", record_normalization)
    monkeypatch.setattr(ground_track, "_convert_inertial_state_to_itrf", convert)

    query = store.earth_fixed_positions(store.snapshot(), (times[0], times[-1]), wait=True)

    assert normalized_names == [source_frame]
    if conversion_frame is None:
        assert not converted_epochs
        expected_positions = states[:, :3]
    else:
        assert converted_epochs == times.tolist()
        expected_positions = states[:, :3] + times[:, None]
    np.testing.assert_allclose(query.value[0].values[:, 1:], expected_positions)


def test_earth_fixed_computes_only_rows_inside_requested_range(monkeypatch) -> None:
    sample_count = 6000
    indices = np.arange(sample_count, dtype=float)
    times = indices
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
    store = _store_with_samples(
        times,
        states,
        np.zeros(sample_count, dtype=np.int64),
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    snapshot = store.snapshot()
    computed_spans = []
    original_write = oem_data_store._write_earth_fixed_chunk

    def record_write(snapshot, frame_name, start, stop, output) -> None:
        computed_spans.append((start, stop))
        original_write(snapshot, frame_name, start, stop, output)

    monkeypatch.setattr(
        oem_data_store, "_write_earth_fixed_chunk", record_write
    )

    query = store.earth_fixed_positions(
        snapshot, (4500.0, 4501.0), wait=True
    )

    assert computed_spans == [(4500, 4502)]
    np.testing.assert_array_equal(query.value[0].values[:, 0], [4500.0, 4501.0])
    assert store._earth_fixed_ready is not None
    np.testing.assert_array_equal(
        np.flatnonzero(store._earth_fixed_ready), [4500, 4501]
    )


def test_nonblocking_earth_fixed_query_reports_pending_coverage(monkeypatch) -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(
        times,
        states,
        segments,
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    snapshot = store.snapshot()
    entered = Event()
    release = Event()
    original_write = oem_data_store._write_earth_fixed_chunk

    def blocked_write(snapshot, frame_name, start, stop, output) -> None:
        entered.set()
        assert release.wait(3)
        original_write(snapshot, frame_name, start, stop, output)

    monkeypatch.setattr(oem_data_store, "_write_earth_fixed_chunk", blocked_write)
    future = None
    bounds = (times[0], times[-1])
    try:
        partial = store.earth_fixed_positions(snapshot, bounds)
        assert entered.wait(3)
        assert partial.value == ()
        assert partial.coverage.covered_s == ()
        assert not partial.coverage.complete
        future = store.prefetch(
            snapshot,
            QueryRequest("earth-fixed", bounds),
        )
    finally:
        release.set()
        if future is not None:
            future.result(timeout=3)
        store.close()


def test_station_profiles_are_lazy_shared_and_threshold_independent() -> None:
    elevations = np.array([0.0, 60.0, 0.0])
    states = np.column_stack(
        (
            6_378_137.0 + np.sin(np.deg2rad(elevations)) * 1_000_000.0,
            np.cos(np.deg2rad(elevations)) * 1_000_000.0,
            np.zeros(3),
            np.zeros((3, 3)),
        )
    )
    store = _store_with_samples(
        np.array([0.0, 60.0, 120.0]),
        states,
        np.zeros(3, dtype=np.int64),
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    snapshot = store.snapshot()

    assert store._station_profiles == {}
    first = store.station_access(snapshot, station, (0.0, 120.0), wait=True)
    profile = first.value.profiles[0].group
    assert profile.columns == (
        "t",
        "azimuth_deg",
        "elevation_deg",
        "range_km",
    )
    tier = next(iter(store._station_profiles.values()))
    assert np.shares_memory(profile.values, tier.buffer)
    assert tier.memo.counters.chunks_computed == 1
    assert not profile.values.flags.writeable
    assert len(first.value.intervals) == 1
    interval = first.value.intervals[0]
    assert 0.0 <= interval.start_s < interval.peak_time_s < interval.end_s <= 120.0
    assert interval.peak_elevation_deg > station.minimum_elevation_deg

    raised_threshold = store.station_access(
        snapshot,
        station,
        (0.0, 120.0),
        minimum_elevation_deg=50,
        wait=True,
    )

    assert raised_threshold.value.station.minimum_elevation_deg == 50
    assert np.shares_memory(
        raised_threshold.value.profiles[0].group.values,
        profile.values,
    )
    assert len(store._station_profiles) == 1
    assert tier.memo.counters.chunks_computed == 1
    assert len(raised_threshold.value.intervals) == 1
    assert (
        raised_threshold.value.intervals[0].peak_elevation_deg
        >= first.value.intervals[0].peak_elevation_deg
    )


def test_station_access_recomputes_policy_dependent_support_margin() -> None:
    times = np.arange(0.0, 12_001.0, 60.0)
    states = np.tile(
        np.array([7_378_137.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        (times.size, 1),
    )
    store = _store_with_samples(
        times,
        states,
        np.zeros(times.size, dtype=np.int64),
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0)
    bounds = (6_000.0, 6_060.0)

    first_snapshot = store.snapshot()
    first = store.station_access(first_snapshot, station, bounds, wait=True)
    first_profile = first.value.profiles[0].group.values
    first_tier = next(iter(store._station_profiles.values()))

    store.set_interpolation(InterpolationPolicy("lagrange", 3))
    next_snapshot = store.snapshot()
    repeated = store.station_access(next_snapshot, station, bounds, wait=True)
    repeated_profile = repeated.value.profiles[0].group.values
    repeated_tier = next(iter(store._station_profiles.values()))

    assert first_profile[0, 0] < bounds[0]
    assert first_profile[-1, 0] > bounds[1]
    margin = max(
        oem_data_store.ACCESS_WINDOW_MIN_MARGIN_S,
        oem_data_store.ACCESS_WINDOW_MARGIN_FRACTION * (bounds[1] - bounds[0]),
    )
    expected_first, expected_stop = oem_data_store._station_profile_row_range(
        first_tier.layouts[0],
        (bounds[0] - margin, bounds[1] + margin),
    )
    assert first_tier.ready is not None
    np.testing.assert_array_equal(
        np.flatnonzero(first_tier.ready),
        np.arange(expected_first, expected_stop),
    )
    np.testing.assert_array_equal(repeated_profile, first_profile)
    assert repeated_tier is not first_tier
    assert first_tier.memo.counters.chunks_computed == 1
    assert repeated_tier.memo.counters.chunks_computed == 1


def test_nonblocking_station_query_reports_pending_coverage(monkeypatch) -> None:
    elevations = np.array([0.0, 60.0, 0.0])
    states = np.column_stack(
        (
            6_378_137.0 + np.sin(np.deg2rad(elevations)) * 1_000_000.0,
            np.cos(np.deg2rad(elevations)) * 1_000_000.0,
            np.zeros(3),
            np.zeros((3, 3)),
        )
    )
    store = _store_with_samples(
        np.array([0.0, 60.0, 120.0]),
        states,
        np.zeros(3, dtype=np.int64),
        metadata=(("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    snapshot = store.snapshot()
    entered = Event()
    release = Event()
    original_metrics = oem_data_store.station_metrics

    def blocked_metrics(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original_metrics(*args, **kwargs)

    monkeypatch.setattr(oem_data_store, "station_metrics", blocked_metrics)
    future = None
    try:
        partial = store.station_access(snapshot, station, (0.0, 120.0))
        assert entered.wait(3)
        assert partial.value.profiles == ()
        assert partial.value.intervals == ()
        assert not partial.coverage.complete
        future = store.prefetch(
            snapshot,
            QueryRequest(
                "station-access",
                (0.0, 120.0),
                station=station,
            ),
        )
    finally:
        release.set()
        if future is not None:
            future.result(timeout=3)
        store.close()


def test_derived_buffer_eviction_waits_for_views_and_recomputes() -> None:
    times, states, segments = _series_samples()
    store = OemDataStore(derived_memory_budget_bytes=1)
    epoch = store.begin(len(times))
    reservation = store.reserve(len(times))
    reservation.raw[:, 0] = times
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = segments
    store.commit(reservation, len(times))
    store.mark_complete(epoch, (), ())
    snapshot = store.snapshot()

    active = store.series(
        snapshot, (times[0], times[-1]), groups=("kinematics",), wait=True
    )
    expected = _one_group(active, "kinematics").values.copy()
    old_memo = store._series_memos["kinematics"]
    assert "kinematics" in store._series_buffers

    competing = store.series(
        snapshot, (times[0], times[-1]), groups=("rtn",), wait=True
    )
    assert "kinematics" in store._series_buffers
    del active
    gc.collect()

    latest = store.series(
        snapshot,
        (times[0], times[-1]),
        groups=("direction-rates",),
        wait=True,
    )
    assert "kinematics" in store._series_buffers
    assert old_memo.state(0, epoch=snapshot.epoch, policy_revision=0) is ChunkState.ABSENT
    assert old_memo.counters.evictions == 1
    np.testing.assert_array_equal(
        _one_group(competing, "rtn").values[:, 0], times
    )
    np.testing.assert_array_equal(
        _one_group(latest, "direction-rates").values[:, 0], times
    )

    recomputed = store.series(
        snapshot, (times[0], times[-1]), groups=("kinematics",), wait=True
    )
    np.testing.assert_array_equal(_one_group(recomputed, "kinematics").values, expected)


def test_pair_view_keeps_its_chunk_pinned_after_parent_views_are_released() -> None:
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    store._derived_memory_budget_bytes = 1
    snapshot = store.snapshot()
    query = store.series(
        snapshot, (times[0], times[-1]), groups=("kinematics",), wait=True
    )
    group = _one_group(query, "kinematics")
    pair = group.pair("t", "speed_m_s")
    memo = store._series_memos["kinematics"]
    del query, group
    gc.collect()

    store.series(snapshot, (times[0], times[-1]), groups=("rtn",), wait=True)
    assert memo.state(0, epoch=snapshot.epoch, policy_revision=0) is ChunkState.COMPLETE
    assert memo.counters.evictions == 0
    np.testing.assert_array_equal(pair[:, 0], times)

    del pair
    gc.collect()
    store.series(
        snapshot,
        (times[0], times[-1]),
        groups=("direction-rates",),
        wait=True,
    )
    assert memo.state(0, epoch=snapshot.epoch, policy_revision=0) is ChunkState.ABSENT
    assert memo.counters.evictions == 1


def test_chunk_eviction_preserves_other_ready_chunks(monkeypatch) -> None:
    monkeypatch.setattr(oem_data_store, "DERIVED_CHUNK_SIZE", 2)
    monkeypatch.setattr(oem_data_store, "_madvise_chunk", lambda *args: None)
    times, states, segments = _series_samples()
    store = _store_with_samples(times, states, segments)
    store._derived_memory_budget_bytes = 1
    snapshot = store.snapshot()
    memo = store._series_storage(snapshot, "kinematics")[1]

    first = store.series(
        snapshot, (times[0], times[1]), groups=("kinematics",), wait=True
    )
    expected_first_chunk = _one_group(first, "kinematics").values.copy()
    del first
    gc.collect()

    second = store.series(
        snapshot, (times[2], times[3]), groups=("kinematics",), wait=True
    )
    assert memo.state(0, epoch=snapshot.epoch, policy_revision=0) is ChunkState.ABSENT
    assert memo.state(1, epoch=snapshot.epoch, policy_revision=0) is ChunkState.COMPLETE
    assert memo.counters.evictions == 1

    recomputed = store.series(
        snapshot, (times[0], times[1]), groups=("kinematics",), wait=True
    )
    np.testing.assert_array_equal(
        _one_group(recomputed, "kinematics").values,
        expected_first_chunk,
    )
    assert memo.state(1, epoch=snapshot.epoch, policy_revision=0) is ChunkState.COMPLETE
    assert len(_one_group(second, "kinematics").values) == 2


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
