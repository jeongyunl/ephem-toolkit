"""Tests for direct-to-store OEM streaming."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import numpy as np
import pytest

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.oem_data_store import LoadStatus, OemDataStore
from ephem_toolkit.play_oem.streaming_oem import (
    OemStreamComplete,
    _Cancelled,
    read_oem_into_store,
)


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


def test_direct_store_stream_matches_one_shot_across_segments(
    tmp_path: Path,
) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    expected = CcsdsOem.from_file(source)
    store = OemDataStore()
    store.begin(8)
    notices = []
    result = read_oem_into_store(
        source, store, batch_size=2, on_append=notices.append, cancel_event=Event()
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


@pytest.mark.parametrize("batch_size", [1, 2, 3, 10])
def test_direct_store_stream_accepts_bounded_flush_sizes(
    tmp_path: Path, batch_size: int
) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    store = OemDataStore()
    store.begin(8)
    result = read_oem_into_store(
        source, store, batch_size=batch_size, on_append=lambda notice: None,
        cancel_event=Event(),
    )
    assert result.state_count == store.snapshot().sample_count == 4


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
            source, store, batch_size=3, on_append=lambda notice: None,
            cancel_event=Event(),
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
            source, store, batch_size=2, on_append=lambda notice: None,
            cancel_event=Event(),
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
    source.write_text(
        OEM_TEXT.replace("REF_FRAME = GCRF", "REF_FRAME = INVALID"), encoding="utf-8"
    )
    store = OemDataStore()
    store.begin(8)
    with pytest.raises(ValueError, match="REF_FRAME"):
        read_oem_into_store(
            source, store, batch_size=3, on_append=lambda notice: None,
            cancel_event=Event(),
        )
    assert store.snapshot().sample_count == 4
    assert store.snapshot().status is LoadStatus.FAILED
    with pytest.raises(ValueError, match="empty store"):
        read_oem_into_store(
            source, store, batch_size=3, on_append=lambda notice: None,
            cancel_event=Event(),
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
        source, store, batch_size=512, on_append=lambda notice: None,
        cancel_event=Event(),
    )
    snapshot = store.snapshot()
    assert result.state_count == len(expected.states) == count
    np.testing.assert_array_equal(snapshot.raw[:, 0], [t for t, _ in expected.states])
    np.testing.assert_array_equal(snapshot.raw[:, 1:], [s for _, s in expected.states])
    np.testing.assert_array_equal(snapshot.segment_ids, expected.segment_ids)


def test_direct_store_stream_keeps_valid_prefix_before_late_parse_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "malformed.oem"
    source.write_text(OEM_TEXT + "COVARIANCE_STOP\n", encoding="utf-8")
    store = OemDataStore()
    store.begin(8)
    with pytest.raises(ValueError, match="COVARIANCE_STOP"):
        read_oem_into_store(
            source, store, batch_size=2, on_append=lambda notice: None,
            cancel_event=Event(),
        )
    snapshot = store.snapshot()
    assert snapshot.sample_count == 4
    assert snapshot.status is LoadStatus.FAILED


def test_direct_store_stream_validates_but_does_not_retain_comments_or_covariance(
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

    store = OemDataStore()
    store.begin(4)
    completion = read_oem_into_store(
        source, store, batch_size=2, on_append=lambda notice: None,
        cancel_event=Event(),
    )
    assert isinstance(completion, OemStreamComplete)
    assert "COMMENT" not in dict(completion.header)
    assert "COMMENT" not in dict(completion.meta)
