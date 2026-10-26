"""Tests for cancellable, generation-tagged OEM load sessions."""

from __future__ import annotations

from pathlib import Path
from threading import get_ident
import time

from ephem_toolkit.play_oem.incremental_loader import (
    IncrementalLoader,
    IncrementalLoadSession,
    LoadEventKind,
)


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
