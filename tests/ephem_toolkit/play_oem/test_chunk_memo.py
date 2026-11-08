"""Tests for the lazy derived-chunk memo."""

from concurrent.futures import CancelledError
from threading import Event, Thread
from time import monotonic

import pytest

from ephem_toolkit.play_oem.chunk_memo import ChunkMemo, ChunkState


def test_complete_chunk_is_cached_and_stamped() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    calls = 0

    def compute() -> int:
        nonlocal calls
        calls += 1
        return 42

    assert memo.state("series:0", epoch=1, policy_revision=0) is ChunkState.ABSENT
    assert (
        memo.get_or_compute(
            "series:0", compute, epoch=1, policy_revision=0
        )
        == 42
    )
    assert memo.state("series:0", epoch=1, policy_revision=0) is ChunkState.COMPLETE
    assert memo.state("series:0", epoch=2, policy_revision=0) is ChunkState.ABSENT
    assert (
        memo.get_or_compute(
            "series:0", compute, epoch=1, policy_revision=0
        )
        == 42
    )
    assert calls == 1
    assert memo.counters.chunks_computed == 1
    assert memo.counters.hits == 1


def test_tentative_chunk_is_recomputed_before_it_becomes_complete() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    calls = 0

    def compute() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert (
        memo.get_or_compute(
            "tail", compute, epoch=1, policy_revision=0, tentative=True
        )
        == 1
    )
    assert memo.state("tail", epoch=1, policy_revision=0) is ChunkState.TENTATIVE
    assert memo.get_or_compute("tail", compute, epoch=1, policy_revision=0) == 2
    assert memo.state("tail", epoch=1, policy_revision=0) is ChunkState.COMPLETE
    assert memo.get_or_compute("tail", compute, epoch=1, policy_revision=0) == 2
    assert calls == 2
    assert memo.counters.chunks_computed == 2
    assert memo.counters.hits == 1
    assert memo.counters.evictions == 1


def test_concurrent_requests_share_one_in_flight_computation() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    started = Event()
    release = Event()
    results: list[int] = []
    errors: list[Exception] = []
    calls = 0

    def compute() -> int:
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(3)
        return 7

    def request() -> None:
        try:
            results.append(
                memo.get_or_compute("chunk", compute, epoch=1, policy_revision=0)
            )
        except Exception as error:
            errors.append(error)

    first = Thread(target=request)
    second = Thread(target=request)
    first.start()
    assert started.wait(3)
    second.start()
    deadline = monotonic() + 3
    while memo.counters.deduplicated == 0 and monotonic() < deadline:
        Event().wait(0.001)
    try:
        assert memo.counters.deduplicated == 1
    finally:
        release.set()
        first.join(3)
        second.join(3)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert sorted(results) == [7, 7]
    assert calls == 1
    assert memo.counters.chunks_computed == 1


def test_invalidating_in_flight_work_prevents_publication() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    started = Event()
    release = Event()
    errors: list[Exception] = []

    def compute() -> int:
        started.set()
        assert release.wait(3)
        return 9

    def request() -> None:
        try:
            memo.get_or_compute("chunk", compute, epoch=1, policy_revision=0)
        except Exception as error:
            errors.append(error)

    worker = Thread(target=request)
    worker.start()
    assert started.wait(3)
    assert memo.state("chunk", epoch=1, policy_revision=0) is ChunkState.COMPUTING
    assert memo.invalidate("chunk")
    release.set()
    worker.join(3)

    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], CancelledError)
    assert memo.state("chunk", epoch=1, policy_revision=0) is ChunkState.ABSENT
    assert memo.counters.chunks_computed == 0


def test_in_flight_timeout_error_is_propagated_to_deduplicated_request() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    started = Event()
    release = Event()
    errors: list[Exception] = []

    def compute() -> int:
        started.set()
        assert release.wait(3)
        raise TimeoutError("chunk computation failed")

    def request() -> None:
        try:
            memo.get_or_compute("chunk", compute, epoch=1, policy_revision=0)
        except Exception as error:
            errors.append(error)

    first = Thread(target=request)
    second = Thread(target=request)
    first.start()
    assert started.wait(3)
    second.start()
    deadline = monotonic() + 3
    while memo.counters.deduplicated == 0 and monotonic() < deadline:
        Event().wait(0.001)
    try:
        assert memo.counters.deduplicated == 1
    finally:
        release.set()
        first.join(3)
        second.join(3)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(errors) == 2
    assert all(isinstance(error, TimeoutError) for error in errors)
    assert memo.state("chunk", epoch=1, policy_revision=0) is ChunkState.ABSENT


def test_cancelled_computation_does_not_publish_partial_result() -> None:
    memo: ChunkMemo[str, int] = ChunkMemo()
    cancelled = Event()
    started = Event()
    release = Event()

    def compute() -> int:
        started.set()
        assert release.wait(3)
        return 11

    errors: list[Exception] = []

    def request() -> None:
        try:
            memo.get_or_compute(
                "chunk",
                compute,
                epoch=1,
                policy_revision=0,
                cancel_event=cancelled,
            )
        except Exception as error:
            errors.append(error)

    worker = Thread(target=request)
    worker.start()
    assert started.wait(3)
    cancelled.set()
    release.set()
    worker.join(3)

    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], CancelledError)
    assert memo.state("chunk", epoch=1, policy_revision=0) is ChunkState.ABSENT
    assert memo.counters.chunks_computed == 0


def test_clear_counts_cached_entries_as_evictions() -> None:
    memo: ChunkMemo[int, int] = ChunkMemo()
    memo.get_or_compute(0, lambda: 1, epoch=1, policy_revision=0)
    memo.get_or_compute(1, lambda: 2, epoch=1, policy_revision=0, tentative=True)

    memo.clear()

    assert memo.state(0, epoch=1, policy_revision=0) is ChunkState.ABSENT
    assert memo.state(1, epoch=1, policy_revision=0) is ChunkState.ABSENT
    assert memo.counters.evictions == 2
