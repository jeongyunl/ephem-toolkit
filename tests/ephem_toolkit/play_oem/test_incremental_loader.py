"""Tests for cancellable, generation-tagged OEM load sessions."""

from __future__ import annotations

from pathlib import Path
from threading import Event, get_ident
import time

import ephem_toolkit.core.ccsds.odm as odm
from ephem_toolkit.play_oem.incremental_loader import (
    IncrementalLoader,
    IncrementalLoadSession,
    LoadEvent,
    LoadEventKind,
)
from ephem_toolkit.play_oem.oem_data_store import LoadStatus, OemDataStore


def _oem_prefix(state_rows: str) -> str:
    return (
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        f"{state_rows}"
    )


def _drain_until_finished(
    session: IncrementalLoadSession, timeout_s: float = 3.0
) -> list:
    deadline = time.monotonic() + timeout_s
    events = []
    while not session.finished and time.monotonic() < deadline:
        events.extend(session.drain())
        time.sleep(0.005)
    events.extend(session.drain())
    assert session.finished
    return events


def test_load_session_tags_batches_and_completion_with_generation(tmp_path: Path) -> None:
    source = tmp_path / "small.oem"
    source.write_text(
        _oem_prefix(
            "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
            "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n"
            "2026-01-01T00:00:20 7000 2 0 0 7.5 0\n"
        ),
        encoding="utf-8",
    )
    session = IncrementalLoadSession(source, generation=42, batch_size=1)
    session.start()
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [
        LoadEventKind.STARTED,
        LoadEventKind.BATCH,
        LoadEventKind.BATCH,
        LoadEventKind.BATCH,
        LoadEventKind.COMPLETE,
    ]
    assert all(event.generation == 42 for event in events)
    assert [event.loaded_state_count for event in events] == [0, 1, 2, 3, 3]


def test_batch_preparation_runs_on_loader_worker(tmp_path: Path) -> None:
    source = tmp_path / "prepared.oem"
    source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    ui_thread = get_ident()
    preparation_threads: list[int] = []

    def prepare(batch) -> int:
        preparation_threads.append(get_ident())
        return len(batch.states)

    session = IncrementalLoadSession(
        source,
        generation=8,
        batch_size=1,
        prepare_batch=prepare,
    )
    session.start()
    events = _drain_until_finished(session)
    batches = [event for event in events if event.kind is LoadEventKind.BATCH]
    assert len(batches) == 1
    assert batches[0].prepared == 1
    assert preparation_threads and preparation_threads[0] != ui_thread


def test_load_session_cancel_releases_backpressure_without_blocking(tmp_path: Path) -> None:
    source = tmp_path / "many.oem"
    rows = "".join(
        f"2026-01-01T00:{index // 60:02d}:{index % 60:02d} 7000 {index} 0 0 7.5 0\n"
        for index in range(1_000)
    )
    source.write_text(_oem_prefix(rows), encoding="utf-8")
    session = IncrementalLoadSession(
        source, generation=7, batch_size=1, queue_size=1
    )
    session.start()
    session.cancel()
    events = _drain_until_finished(session)
    assert events[0].kind is LoadEventKind.STARTED
    assert all(event.kind is LoadEventKind.BATCH for event in events[1:])
    assert len(events) <= 2
    assert session.cancelled


def test_load_session_reports_reader_failure_as_event(tmp_path: Path) -> None:
    source = tmp_path / "bad.oem"
    source.write_text(_oem_prefix("COVARIANCE_STOP\n"), encoding="utf-8")
    session = IncrementalLoadSession(source, generation=9, batch_size=1)
    session.start()
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [
        LoadEventKind.STARTED,
        LoadEventKind.FAILED,
    ]
    assert events[-1].generation == 9
    assert events[-1].error is not None


def test_incremental_loader_can_publish_direct_store_appends(tmp_path: Path) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(
        _oem_prefix(
            "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
            "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n"
            "2026-01-01T00:00:20 7000 2 0 0 7.5 0\n"
        ),
        encoding="utf-8",
    )
    store = OemDataStore()
    loader = IncrementalLoader(batch_size=2, queue_size=8)
    assert store.capacity_for_file(source) >= 3
    session = loader.start(source, store=store)
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [
        LoadEventKind.STARTED,
        LoadEventKind.RAW_APPEND,
        LoadEventKind.RAW_APPEND,
        LoadEventKind.COMPLETE,
    ]
    assert [event.loaded_state_count for event in events] == [0, 2, 3, 3]
    assert all(event.generation == session.generation for event in events)
    assert all(event.raw_notice is not None for event in events[1:3])
    assert store.snapshot().sample_count == 3


def test_automatic_capacity_scan_runs_on_worker_and_cancels(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "direct.oem"
    source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    scan_started = Event()
    release_scan = Event()
    scan_threads: list[int] = []
    capacity_for_file = OemDataStore.capacity_for_file

    def blocked_capacity_scan(path, *, cancel_event=None) -> int:
        scan_threads.append(get_ident())
        scan_started.set()
        assert release_scan.wait(3.0)
        return capacity_for_file(path, cancel_event=cancel_event)

    monkeypatch.setattr(
        OemDataStore, "capacity_for_file", staticmethod(blocked_capacity_scan)
    )
    store = OemDataStore()
    loader = IncrementalLoader()
    calling_thread = get_ident()
    session = loader.start(source, store=store)
    assert scan_started.wait(1.0)
    assert store.capacity == 0
    assert store.status is LoadStatus.LOADING
    assert scan_threads and scan_threads[0] != calling_thread

    session.cancel()
    release_scan.set()
    assert session._finished.wait(3.0)
    assert store.status is LoadStatus.CANCELLED


def test_automatic_capacity_scan_failure_marks_store_failed(tmp_path: Path) -> None:
    store = OemDataStore()
    session = IncrementalLoader().start(tmp_path / "missing.oem", store=store)
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [
        LoadEventKind.STARTED,
        LoadEventKind.FAILED,
    ]
    assert store.status is LoadStatus.FAILED


def test_incremental_loader_replacement_invalidates_old_store_epoch(
    tmp_path: Path,
) -> None:
    slow_source = tmp_path / "many-direct.oem"
    rows = "".join(
        f"2026-01-01T00:{index // 60:02d}:{index % 60:02d} 7000 {index} 0 0 7.5 0\n"
        for index in range(1_000)
    )
    slow_source.write_text(_oem_prefix(rows), encoding="utf-8")
    fast_source = tmp_path / "small-direct.oem"
    fast_source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 9 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    store = OemDataStore()
    loader = IncrementalLoader(batch_size=1, queue_size=1)
    old_session = loader.start(slow_source, store=store, store_capacity=1_000)
    new_session = loader.start(fast_source, store=store, store_capacity=1)
    assert old_session.cancelled
    assert old_session._finished.wait(3.0)
    events = _drain_until_finished(new_session)
    assert all(event.generation == new_session.generation for event in events)
    assert any(event.kind is LoadEventKind.COMPLETE for event in events)
    snapshot = store.snapshot()
    assert snapshot.sample_count == 1
    assert snapshot.raw[0, 1] == 7_000_000.0
    assert snapshot.epoch > old_session._store_epoch


def test_incremental_load_session_cancel_invalidates_its_store_epoch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cancel-direct.oem"
    source.write_text(
        _oem_prefix(
            "".join(
                f"2026-01-01T00:{index // 60:02d}:{index % 60:02d} "
                f"7000 {index} 0 0 7.5 0\n"
                for index in range(1_000)
            )
        ),
        encoding="utf-8",
    )
    store = OemDataStore()
    loader = IncrementalLoader(batch_size=1, queue_size=1)
    session = loader.start(source, store=store, store_capacity=1_000)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and store.snapshot().sample_count == 0:
        time.sleep(0.001)
    assert store.snapshot().sample_count > 0
    session.cancel()
    assert session._finished.wait(3.0)
    snapshot = store.snapshot()
    assert snapshot.status is LoadStatus.CANCELLED
    assert snapshot.sample_count > 0


def test_incremental_loader_failure_keeps_prefix_and_reports_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "late-error-direct.oem"
    source.write_text(
        _oem_prefix(
            "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
            "2026-01-01T00:00:10 7000 invalid 0 0 7.5 0\n"
        ),
        encoding="utf-8",
    )
    store = OemDataStore()
    loader = IncrementalLoader(batch_size=1, queue_size=4)
    session = loader.start(source, store=store, store_capacity=4)
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [
        LoadEventKind.STARTED,
        LoadEventKind.RAW_APPEND,
        LoadEventKind.FAILED,
    ]
    assert events[-1].error is not None
    assert store.snapshot().sample_count == 1
    assert store.snapshot().status is LoadStatus.FAILED


def test_loader_replacement_ignores_events_from_canceled_generation(
    tmp_path: Path,
) -> None:
    slow_source = tmp_path / "many.oem"
    rows = "".join(
        f"2026-01-01T00:{index // 60:02d}:{index % 60:02d} 7000 {index} 0 0 7.5 0\n"
        for index in range(1_000)
    )
    slow_source.write_text(_oem_prefix(rows), encoding="utf-8")
    fast_source = tmp_path / "small.oem"
    fast_source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    loader = IncrementalLoader(batch_size=1, queue_size=1)
    old_session = loader.start(slow_source)
    new_session = loader.start(fast_source)
    assert old_session.cancelled
    assert new_session.generation == loader.generation == 2

    events = _drain_until_finished(new_session)
    assert events
    assert all(event.generation == 2 for event in events)
    assert all(event.generation == loader.generation for event in loader.drain())


def test_loader_drain_discards_stale_event_kinds(tmp_path: Path) -> None:
    source = tmp_path / "small.oem"
    source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    entered = Event()
    release = Event()

    def prepare(batch):
        entered.set()
        if not release.wait(3.0):
            raise TimeoutError("test preparation was not released")
        return len(batch.states)

    loader = IncrementalLoader(batch_size=1, queue_size=4)
    old_session = loader.start(source, prepare_batch=prepare)
    try:
        assert entered.wait(3.0)
        new_session = loader.start(source, prepare_batch=prepare)
        loader.drain()
        for kind in (LoadEventKind.BATCH, LoadEventKind.COMPLETE, LoadEventKind.FAILED):
            new_session._events.put_nowait(LoadEvent(old_session.generation, kind, 0))
        assert loader.drain() == []
        release.set()
        events = _drain_until_finished(new_session)
        assert any(event.kind is LoadEventKind.COMPLETE for event in events)
        assert all(event.generation == loader.generation for event in events)
    finally:
        loader.cancel()
        release.set()
        assert old_session._finished.wait(3.0)


def test_cancel_during_preparation_discards_unpublished_batch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "prepared.oem"
    source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )
    started = Event()
    release = Event()

    def prepare(batch):
        started.set()
        if not release.wait(3.0):
            raise TimeoutError("test preparation was not released")
        return len(batch.states)

    session = IncrementalLoadSession(
        source, generation=10, batch_size=1, prepare_batch=prepare
    )
    session.start()
    try:
        assert started.wait(3.0)
        session.cancel()
    finally:
        release.set()
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [LoadEventKind.STARTED]


def test_cancel_during_parsing_rejects_late_batch(
    monkeypatch, tmp_path: Path
) -> None:
    entered = Event()
    release = Event()
    original_validate = odm.validate_odm_line
    source = tmp_path / "parsing.oem"
    source.write_text(
        _oem_prefix("2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"),
        encoding="utf-8",
    )

    def blocked_validate(line, label):
        if not entered.is_set():
            entered.set()
            if not release.wait(3.0):
                raise TimeoutError("test parser was not released")
        return original_validate(line, label)

    monkeypatch.setattr(odm, "validate_odm_line", blocked_validate)
    session = IncrementalLoadSession(source, generation=11)
    session.start()
    try:
        assert entered.wait(3.0)
        session.cancel()
    finally:
        release.set()
    events = _drain_until_finished(session)
    assert [event.kind for event in events] == [LoadEventKind.STARTED]
