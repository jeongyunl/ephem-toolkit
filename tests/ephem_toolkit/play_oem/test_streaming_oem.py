"""Tests for bounded background OEM reading."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
import numpy as np

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.oem_data_store import LoadStatus, OemDataStore
from ephem_toolkit.play_oem.streaming_oem import (
    OemStreamComplete,
    OemStreamError,
    _Cancelled,
    iter_oem_events,
    read_oem_into_store,
)
from ephem_toolkit.play_oem.playback_data import AppendablePlaybackData
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


OEM_TEXT = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2026-01-01T00:00:00
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST
OBJECT_ID = 2026-001A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:00:00 7000 0 0 0 7.5 0
2026-01-01T00:00:10 7000 1 0 0 7.5 0
2026-01-01T00:00:20 7000 2 0 0 7.5 0
META_START
OBJECT_NAME = TEST
OBJECT_ID = 2026-001A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:10:00 7000 3 0 0 7.5 0
"""


def test_stream_matches_whole_file_parse_across_segment_and_batch_boundaries(
    tmp_path: Path,
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    parsed = CcsdsOem.from_file(source)

    events = list(iter_oem_events(source, batch_size=2, queue_size=1))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    completed = events[-1]

    assert isinstance(completed, OemStreamComplete)
    assert [len(batch.states) for batch in batches] == [2, 2]
    assert completed.state_count == len(parsed.states)
    assert dict(completed.meta)["OBJECT_NAME"] == parsed.meta.object_name
    assert [
        segment_id for batch in batches for segment_id in batch.segment_ids
    ] == parsed.segment_ids
    streamed_states = [state for batch in batches for state in batch.states]
    for actual, expected in zip(streamed_states, parsed.states):
        assert actual[0] == expected[0]
        assert (actual[1] == expected[1]).all()


@pytest.mark.parametrize("batch_size", [1, 2, 3, 10])
def test_direct_store_stream_matches_one_shot_across_segments(
    tmp_path: Path, batch_size: int
) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    expected = CcsdsOem.from_file(source)
    store = OemDataStore()
    store.begin(8)
    notices = []
    result = read_oem_into_store(
        source, store, batch_size=batch_size, on_append=notices.append, cancel_event=Event()
    )
    snapshot = store.snapshot()
    assert result.state_count == snapshot.sample_count == 4
    assert dict(result.meta)["OBJECT_NAME"] == expected.meta.object_name
    np.testing.assert_array_equal(snapshot.raw[:, 0], [t for t, _ in expected.states])
    np.testing.assert_array_equal(snapshot.raw[:, 1:], [s for _, s in expected.states])
    np.testing.assert_array_equal(snapshot.segment_ids, expected.segment_ids)
    np.testing.assert_array_equal(snapshot.segment_bounds, [[0, 3], [3, 4]])
    assert snapshot.status is LoadStatus.COMPLETE
    assert dict(snapshot.meta)["OBJECT_NAME"] == "TEST"
    assert snapshot.failure is None
    assert notices[-1].sample_count == 4
    assert all(notice.epoch == snapshot.epoch for notice in notices)


def test_direct_store_stream_does_not_allocate_per_state_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    store = OemDataStore()
    store.begin(4)

    def reject_array(*args, **kwargs):
        raise AssertionError("direct ingestion must not allocate state arrays")

    monkeypatch.setattr("ephem_toolkit.core.ccsds.oem.np.array", reject_array)
    result = read_oem_into_store(
        source, store, batch_size=2, on_append=lambda notice: None, cancel_event=Event()
    )
    assert result.state_count == 4


@pytest.mark.parametrize(
    "tail",
    [
        "2026-01-01T00:20:00 7000 bad 0 0 7.5 0\n",
        "COVARIANCE_START\n",
        "COVARIANCE_STOP\n",
    ],
)
def test_direct_store_stream_exposes_failures_and_discards_unpublished_rows(
    tmp_path: Path, tail: str
) -> None:
    source = tmp_path / "bad.oem"
    source.write_text(OEM_TEXT + tail, encoding="utf-8")
    store = OemDataStore()
    store.begin(8)
    with pytest.raises(ValueError):
        read_oem_into_store(
            source, store, batch_size=3, on_append=lambda notice: None, cancel_event=Event()
        )
    assert store.snapshot().sample_count == 3
    assert store.snapshot().status is LoadStatus.FAILED
    assert store.snapshot().raw.shape == (3, 7)


def test_direct_store_stream_cancellation_and_capacity_are_explicit(tmp_path: Path) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    store = OemDataStore()
    store.begin(4)
    cancelled = Event()
    with pytest.raises(_Cancelled):
        read_oem_into_store(
            source, store, batch_size=2, on_append=lambda notice: cancelled.set(),
            cancel_event=cancelled,
        )
    assert store.snapshot().sample_count == 2
    assert store.snapshot().status is LoadStatus.CANCELLED
    store.begin(3)
    with pytest.raises(OverflowError, match="capacity"):
        read_oem_into_store(
            source, store, batch_size=2, on_append=lambda notice: None, cancel_event=Event()
        )
    assert store.snapshot().sample_count == 3
    assert store.snapshot().status is LoadStatus.FAILED


def test_direct_store_stream_early_cancellation_and_observer_failure(tmp_path: Path) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    store = OemDataStore()
    store.begin(8)
    cancelled = Event()
    cancelled.set()
    with pytest.raises(_Cancelled):
        read_oem_into_store(
            source, store, batch_size=2, on_append=lambda notice: None,
            cancel_event=cancelled,
        )
    assert store.snapshot().sample_count == 0
    assert store.snapshot().status is LoadStatus.CANCELLED
    store.begin(8)

    def reject_notice(notice) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        read_oem_into_store(
            source, store, batch_size=2, on_append=reject_notice, cancel_event=Event()
        )
    assert store.snapshot().sample_count == 2
    assert store.snapshot().status is LoadStatus.FAILED
    assert store.snapshot().raw.shape == (2, 7)


def test_direct_store_stream_cannot_continue_after_epoch_replacement(tmp_path: Path) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    store = OemDataStore()
    store.begin(8)

    def replace_epoch(notice) -> None:
        store.begin(8)

    with pytest.raises(RuntimeError, match="epoch has changed"):
        read_oem_into_store(
            source, store, batch_size=2, on_append=replace_epoch, cancel_event=Event()
        )
    assert store.snapshot().sample_count == 0


def test_direct_store_stream_context_failure_is_not_completion(tmp_path: Path) -> None:
    source = tmp_path / "bad-context.oem"
    source.write_text(OEM_TEXT.replace("REF_FRAME = GCRF", "REF_FRAME = INVALID"), encoding="utf-8")
    store = OemDataStore()
    store.begin(8)
    with pytest.raises(ValueError, match="REF_FRAME"):
        read_oem_into_store(
            source, store, batch_size=3, on_append=lambda notice: None, cancel_event=Event()
        )
    assert store.snapshot().sample_count == 4
    assert store.snapshot().status is LoadStatus.FAILED
    with pytest.raises(ValueError, match="empty store"):
        read_oem_into_store(
            source, store, batch_size=3, on_append=lambda notice: None, cancel_event=Event()
        )


@pytest.mark.parametrize(
    "filename,count", [("ISS_2026-05-20.OEM", 5402), ("JPSS-1.oem", 21601)]
)
def test_direct_store_stream_matches_real_fixture(filename: str, count: int) -> None:
    source = Path("tests/data") / filename
    expected = CcsdsOem.from_file(source)
    store = OemDataStore()
    store.begin(count)
    result = read_oem_into_store(
        source, store, batch_size=512, on_append=lambda notice: None, cancel_event=Event()
    )
    snapshot = store.snapshot()
    assert result.state_count == len(expected.states) == count
    np.testing.assert_array_equal(snapshot.raw[:, 0], [t for t, _ in expected.states])
    np.testing.assert_array_equal(snapshot.raw[:, 1:], [s for _, s in expected.states])
    np.testing.assert_array_equal(snapshot.segment_ids, expected.segment_ids)


def test_stream_yields_valid_prefix_before_late_parse_error(tmp_path: Path) -> None:
    source = tmp_path / "malformed.oem"
    source.write_text(OEM_TEXT + "COVARIANCE_STOP\n", encoding="utf-8")
    events = iter_oem_events(source, batch_size=2)

    first_batch = next(events)
    assert len(first_batch.states) == 2
    with pytest.raises(OemStreamError, match="COVARIANCE_STOP"):
        list(events)


def test_stream_validates_but_does_not_retain_comments_or_covariance(
    tmp_path: Path,
) -> None:
    source = tmp_path / "comments-and-covariance.oem"
    content = OEM_TEXT.replace(
        "CCSDS_OEM_VERS = 2.0\n",
        "CCSDS_OEM_VERS = 2.0\nCOMMENT header\n",
        1,
    ).replace(
        "META_START\nOBJECT_NAME = TEST\n",
        "META_START\nCOMMENT metadata\nOBJECT_NAME = TEST\n",
        1,
    ).replace(
        "META_STOP\n2026-01-01T00:00:00",
        "META_STOP\nCOMMENT ephemeris\n2026-01-01T00:00:00",
        1,
    )
    content += (
        "COVARIANCE_START\n"
        "COMMENT covariance\n"
        "EPOCH = 2026-01-01T00:00:00\n"
        "COV_REF_FRAME = GCRF\n"
        "1\n2 3\n4 5 6\n7 8 9 10\n11 12 13 14 15\n"
        "16 17 18 19 20 21\n"
        "COVARIANCE_STOP\n"
    )
    source.write_text(content, encoding="utf-8")
    parsed = CcsdsOem.from_file(source)
    assert parsed.header.comments == ["header"]
    assert parsed.meta.comments == ["metadata"]
    assert parsed.data_comments == ["ephemeris"]
    assert len(parsed.covariances) == 1

    events = list(iter_oem_events(source, batch_size=2))
    completion = events[-1]
    assert isinstance(completion, OemStreamComplete)
    assert "COMMENT" not in dict(completion.header)
    assert "COMMENT" not in dict(completion.meta)


def test_stream_iterator_close_cancels_backpressured_worker(tmp_path: Path) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = iter_oem_events(source, batch_size=1, queue_size=1)

    next(events)
    events.close()


def test_stream_rejects_invalid_batch_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        list(iter_oem_events(tmp_path / "unused.oem", batch_size=0))


@pytest.mark.parametrize("batch_size", [1, 2, 3, 100])
def test_appendable_playback_data_matches_one_shot_series_and_cursor(
    tmp_path: Path, batch_size: int
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = list(iter_oem_events(source, batch_size=batch_size))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    complete = events[-1]
    assert isinstance(complete, OemStreamComplete)

    first = batches[0]
    store = AppendablePlaybackData.from_batch(
        first,
        center_name=str(dict(first.meta)["CENTER_NAME"]),
        frame_name=str(dict(first.meta)["REF_FRAME"]),
        interpolation_method="linear",
    )
    for batch in batches[1:]:
        store.append_batch(batch)

    parsed = CcsdsOem.from_file(source)
    expected = compute_orbit_series(
        [timestamp for timestamp, _ in parsed.states],
        [state for _, state in parsed.states],
        TimeUnit.MINUTES,
        parsed.segment_ids,
    )
    for name in expected.__dataclass_fields__:
        np.testing.assert_allclose(
            getattr(store.series, name), getattr(expected, name), equal_nan=True
        )
    np.testing.assert_array_equal(
        store.timestamps_s, [timestamp for timestamp, _ in parsed.states]
    )
    np.testing.assert_array_equal(store.segment_ids, parsed.segment_ids)
    np.testing.assert_allclose(
        store.ground_track_source.states_m,
        np.asarray([state for _, state in parsed.states]),
    )
    assert store.cursor.lookup(parsed.states[1][0]).status.value == "exact_sample"
    assert store.cursor.lookup((parsed.states[0][0] + parsed.states[1][0]) / 2).status.value == "interpolated"


def test_appendable_cursor_matches_one_shot_hermite_interpolation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = list(iter_oem_events(source, batch_size=1))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    first = batches[0]
    store = AppendablePlaybackData.from_batch(
        first,
        center_name="EARTH",
        frame_name="GCRF",
        interpolation_method="hermite",
        interpolation_degree=5,
    )
    for batch in batches[1:]:
        store.append_batch(batch)

    parsed = CcsdsOem.from_file(source)
    expected_cursor = OemCursor(
        [timestamp for timestamp, _ in parsed.states],
        [state for _, state in parsed.states],
        interpolation="hermite",
        interpolation_degree=5,
        segment_ids=parsed.segment_ids,
    )
    query_time = (parsed.states[0][0] + parsed.states[1][0]) / 2
    np.testing.assert_allclose(
        store.cursor.lookup(query_time).state_m,
        expected_cursor.lookup(query_time).state_m,
        rtol=0.0,
        atol=1e-8,
    )


def test_appendable_store_switches_time_units_when_loaded_span_crosses_hour() -> None:
    from ephem_toolkit.core.ccsds.oem import OemStateBatch

    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    first = OemStateBatch(((0.0, state),), (0,), (), ())
    store = AppendablePlaybackData.from_batch(
        first, center_name="EARTH", frame_name="GCRF", interpolation_method="linear"
    )
    store.append_batch(OemStateBatch(((1800.0, state),), (0,), (), ()))
    assert store.time_unit is TimeUnit.MINUTES
    store.append_batch(OemStateBatch(((4000.0, state),), (0,), (), ()))
    assert store.time_unit is TimeUnit.HOURS
    np.testing.assert_allclose(store.series.elapsed_time, [0.0, 0.5, 4000.0 / 3600.0])


def test_appendable_store_rejects_out_of_order_batch_without_changing_count() -> None:
    from ephem_toolkit.core.ccsds.oem import OemStateBatch

    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    store = AppendablePlaybackData.from_batch(
        OemStateBatch(((10.0, state),), (0,), (), ()),
        center_name="EARTH",
        frame_name="GCRF",
        interpolation_method="linear",
    )
    with pytest.raises(ValueError, match="follow loaded timestamps"):
        store.append_batch(OemStateBatch(((10.0, state),), (0,), (), ()))
    assert store.source_sample_count == 1
