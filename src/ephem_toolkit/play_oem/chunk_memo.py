"""Thread-safe memoization for lazily computed derived-data chunks."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from concurrent.futures import CancelledError, Future, TimeoutError
from dataclasses import dataclass
from enum import Enum
from threading import Event, RLock
from typing import Generic, TypeVar, cast


K = TypeVar("K", bound=Hashable)
T = TypeVar("T")
_MISSING = object()


class ChunkState(str, Enum):
    """Observable state of one chunk for a specific epoch and policy."""

    ABSENT = "absent"
    COMPUTING = "computing"
    COMPLETE = "complete"
    TENTATIVE = "tentative"


@dataclass(frozen=True)
class ChunkMemoCounters:
    """Cumulative work and reuse counts for a chunk memo."""

    chunks_computed: int
    hits: int
    deduplicated: int
    evictions: int


@dataclass
class _ChunkEntry(Generic[T]):
    epoch: int
    policy_revision: int
    state: ChunkState
    future: Future[T] | None = None
    value: object = _MISSING


class ChunkMemo(Generic[K, T]):
    """Deduplicate chunk work and publish results only for the active stamp.

    A tentative result is returned to its first caller but recomputed on the next
    request. Clearing or replacing a stamp prevents an in-flight computation from
    becoming visible as complete. A caller's cancellation event prevents result
    publication; computations that need prompt interruption should observe that
    event in their callback.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: dict[K, _ChunkEntry[T]] = {}
        self._chunks_computed = 0
        self._hits = 0
        self._deduplicated = 0
        self._evictions = 0

    @property
    def counters(self) -> ChunkMemoCounters:
        """Return a consistent snapshot of cumulative memo counters."""
        with self._lock:
            return ChunkMemoCounters(
                self._chunks_computed,
                self._hits,
                self._deduplicated,
                self._evictions,
            )

    def state(self, key: K, *, epoch: int, policy_revision: int) -> ChunkState:
        """Return the matching entry's state, or ``ABSENT`` for a stale/missing key."""
        with self._lock:
            entry = self._entries.get(key)
            if (
                entry is None
                or entry.epoch != epoch
                or entry.policy_revision != policy_revision
            ):
                return ChunkState.ABSENT
            return entry.state

    def get_or_compute(
        self,
        key: K,
        compute: Callable[[], T],
        *,
        epoch: int,
        policy_revision: int,
        tentative: bool = False,
        cancel_event: Event | None = None,
    ) -> T:
        """Return a complete value or compute one shared in-flight result."""
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()

        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and (
                entry.epoch != epoch or entry.policy_revision != policy_revision
            ):
                self._remove_entry_locked(key, entry)
                entry = None

            if entry is not None and entry.state is ChunkState.COMPLETE:
                self._hits += 1
                return cast(T, entry.value)

            if entry is not None and entry.state is ChunkState.COMPUTING:
                assert entry.future is not None
                future = entry.future
                self._deduplicated += 1
                owner = False
            else:
                if entry is not None and entry.state is ChunkState.TENTATIVE:
                    self._evictions += 1
                future = Future()
                entry = _ChunkEntry(
                    epoch=epoch,
                    policy_revision=policy_revision,
                    state=ChunkState.COMPUTING,
                    future=future,
                )
                self._entries[key] = entry
                owner = True

        if not owner:
            return self._wait_for_result(future, cancel_event)

        try:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            value = compute()
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            with self._lock:
                if self._entries.get(key) is not entry or future.cancelled():
                    raise CancelledError()
                entry.value = value
                entry.state = ChunkState.TENTATIVE if tentative else ChunkState.COMPLETE
                entry.future = None
                self._chunks_computed += 1
                future.set_result(value)
            return value
        except BaseException as error:
            with self._lock:
                if self._entries.get(key) is entry:
                    del self._entries[key]
                if not future.done():
                    future.set_exception(error)
            raise

    def invalidate(self, key: K) -> bool:
        """Remove one memo entry and cancel any waiters for its in-flight result."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            self._remove_entry_locked(key, entry)
            return True

    def discard(self, key: K) -> bool:
        """Remove one entry without counting replacement as a memory eviction."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            self._remove_entry_locked(key, entry, count_eviction=False)
            return True

    def record_hit(self) -> None:
        """Record reuse of data tracked outside this memo's cached value."""
        with self._lock:
            self._hits += 1

    def evict(
        self,
        key: K,
        release: Callable[[], None],
        *,
        epoch: int,
        policy_revision: int,
    ) -> bool:
        """Release one completed chunk before invalidating it atomically."""
        with self._lock:
            entry = self._entries.get(key)
            if (
                entry is None
                or entry.epoch != epoch
                or entry.policy_revision != policy_revision
                or entry.state not in (ChunkState.COMPLETE, ChunkState.TENTATIVE)
            ):
                return False
            release()
            self._remove_entry_locked(key, entry)
            return True

    def clear(self) -> None:
        """Invalidate all entries, including computations still in flight."""
        with self._lock:
            entries = tuple(self._entries.items())
            self._entries.clear()
            for _, entry in entries:
                if entry.state is ChunkState.COMPUTING:
                    if entry.future is not None:
                        entry.future.cancel()
                else:
                    self._evictions += 1

    def _remove_entry_locked(
        self, key: K, entry: _ChunkEntry[T], *, count_eviction: bool = True
    ) -> None:
        if self._entries.get(key) is not entry:
            return
        del self._entries[key]
        if entry.state is ChunkState.COMPUTING:
            if entry.future is not None:
                entry.future.cancel()
        elif count_eviction:
            self._evictions += 1

    @staticmethod
    def _wait_for_result(future: Future[T], cancel_event: Event | None) -> T:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            try:
                return future.result(timeout=0.05)
            except TimeoutError:
                if future.done():
                    return future.result()
                continue
