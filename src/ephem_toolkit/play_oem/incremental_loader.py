"""Cancellable background sessions for progressive OEM loading."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread

from ephem_toolkit.core.ccsds.oem import OemStateBatch

from .streaming_oem import (
    OemStreamComplete,
    OemStreamError,
    _Cancelled as _StreamCancelled,
    read_oem_batches,
    read_oem_into_store,
)
from .oem_data_store import OemDataStore, RawAppendNotice


class LoadEventKind(str, Enum):
    """Kinds of messages a load session delivers to its owner."""

    STARTED = "started"
    BATCH = "batch"
    RAW_APPEND = "raw_append"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class LoadEvent:
    """Immutable event tagged with the file-selection generation that produced it."""

    generation: int
    kind: LoadEventKind
    loaded_state_count: int
    batch: OemStateBatch | None = None
    raw_notice: RawAppendNotice | None = None
    prepared: object | None = None
    completion: OemStreamComplete | None = None
    error: OemStreamError | None = None


class _Cancelled(Exception):
    """Internal signal used when a session's bounded event queue is canceled."""


class IncrementalLoadSession:
    """Read a file off-thread and expose bounded events for consumer polling.

    The optional store mode streams committed raw-row notices instead of
    constructing legacy ``OemStateBatch`` objects.
    """

    def __init__(
        self,
        source: str | Path,
        generation: int,
        *,
        batch_size: int = 512,
        batch_interval_s: float = 0.1,
        queue_size: int = 2,
        prepare_batch: Callable[[OemStateBatch], object] | None = None,
        store: OemDataStore | None = None,
        store_epoch: int | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        if batch_interval_s <= 0.0:
            raise ValueError("batch_interval_s must be positive")
        if (store is None) != (store_epoch is None):
            raise ValueError("store and store_epoch must be supplied together")
        if store is not None and prepare_batch is not None:
            raise ValueError("direct store loading cannot prepare legacy batches")
        self.source = Path(source)
        self.generation = generation
        self.batch_size = batch_size
        self.batch_interval_s = batch_interval_s
        self._prepare_batch = prepare_batch
        self._store = store
        self._store_epoch = store_epoch
        self._cancelled = Event()
        self._finished = Event()
        self._events: Queue[LoadEvent] = Queue(maxsize=queue_size)
        self._worker = Thread(
            target=self._run,
            name=f"play-oem-load-{generation}",
            daemon=True,
        )

    @property
    def finished(self) -> bool:
        """Whether the worker has stopped parsing and publishing events."""
        return self._finished.is_set()

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._cancelled.is_set()

    def start(self) -> None:
        """Start the loader worker once."""
        if self._worker.ident is not None:
            raise RuntimeError("load session has already been started")
        self._events.put_nowait(
            LoadEvent(self.generation, LoadEventKind.STARTED, 0)
        )
        self._worker.start()

    def cancel(self) -> None:
        """Request cancellation without waiting for the reader or GUI thread."""
        self._cancelled.set()
        if self._store is not None and self._store_epoch is not None:
            self._store.cancel_if_epoch(self._store_epoch)

    def drain(self, limit: int | None = None) -> list[LoadEvent]:
        """Return currently queued events without blocking the caller."""
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        drained: list[LoadEvent] = []
        while limit is None or len(drained) < limit:
            try:
                drained.append(self._events.get_nowait())
            except Empty:
                break
        return drained

    def _publish(self, event: LoadEvent) -> None:
        while not self._cancelled.is_set():
            try:
                self._events.put(event, timeout=0.1)
                return
            except Full:
                continue
        raise _Cancelled

    def _run(self) -> None:
        loaded_state_count = 0

        def deliver_batch(batch: OemStateBatch) -> None:
            nonlocal loaded_state_count
            prepared = (
                self._prepare_batch(batch) if self._prepare_batch is not None else None
            )
            loaded_state_count += len(batch.states)
            self._publish(
                LoadEvent(
                    self.generation,
                    LoadEventKind.BATCH,
                    loaded_state_count,
                    batch=batch,
                    prepared=prepared,
                )
            )

        def deliver_raw_append(notice: RawAppendNotice) -> None:
            nonlocal loaded_state_count
            loaded_state_count = notice.sample_count
            self._publish(
                LoadEvent(
                    self.generation,
                    LoadEventKind.RAW_APPEND,
                    loaded_state_count,
                    raw_notice=notice,
                )
            )

        try:
            if self._store is None:
                completion = read_oem_batches(
                    self.source,
                    batch_size=self.batch_size,
                    batch_interval_s=self.batch_interval_s,
                    on_batch=deliver_batch,
                    cancel_event=self._cancelled,
                )
            else:
                assert self._store_epoch is not None
                if self._store.epoch != self._store_epoch:
                    raise RuntimeError("store epoch has changed")
                if self._store.capacity == 0:
                    try:
                        capacity = OemDataStore.capacity_for_file(
                            self.source, cancel_event=self._cancelled
                        )
                    except InterruptedError:
                        if self._cancelled.is_set():
                            return
                        raise
                    if self._cancelled.is_set() or not self._store.allocate_if_epoch(
                        self._store_epoch, capacity
                    ):
                        return
                completion = read_oem_into_store(
                    self.source,
                    self._store,
                    batch_size=self.batch_size,
                    batch_interval_s=self.batch_interval_s,
                    on_append=deliver_raw_append,
                    cancel_event=self._cancelled,
                    expected_epoch=self._store_epoch,
                )
            self._publish(
                LoadEvent(
                    self.generation,
                    LoadEventKind.COMPLETE,
                    completion.state_count,
                    completion=completion,
                )
            )
        except _StreamCancelled:
            pass
        except _Cancelled:
            pass
        except OemStreamError as error:
            if self._store is not None and self._store_epoch is not None:
                self._store.mark_failed(self._store_epoch, error)
            try:
                self._publish(
                    LoadEvent(
                        self.generation,
                        LoadEventKind.FAILED,
                        loaded_state_count,
                        error=error,
                    )
                )
            except _Cancelled:
                pass
        except Exception as error:
            if self._store is not None and self._store_epoch is not None:
                self._store.mark_failed(self._store_epoch, error)
            try:
                self._publish(
                    LoadEvent(
                        self.generation,
                        LoadEventKind.FAILED,
                        loaded_state_count,
                        error=OemStreamError(error),
                    )
                )
            except _Cancelled:
                pass
        except _Cancelled:
            pass
        finally:
            self._finished.set()


class IncrementalLoader:
    """Own the current session and invalidate prior generations on replacement."""

    def __init__(self, *, batch_size: int = 512, queue_size: int = 2) -> None:
        self.batch_size = batch_size
        self.queue_size = queue_size
        self._generation = 0
        self._session: IncrementalLoadSession | None = None

    @property
    def generation(self) -> int:
        """Current generation, including when no session is active."""
        return self._generation

    @property
    def session(self) -> IncrementalLoadSession | None:
        """Current load session, if a source has been selected."""
        return self._session

    def start(
        self,
        source: str | Path,
        *,
        prepare_batch: Callable[[OemStateBatch], object] | None = None,
        store: OemDataStore | None = None,
        store_capacity: int | None = None,
    ) -> IncrementalLoadSession:
        """Start a generation, optionally sizing and ingesting into a raw store.

        If ``store_capacity`` is omitted, the source is synchronously scanned for
        physical lines to derive a safe upper bound before starting the worker.
        """
        if store is None and store_capacity is not None:
            raise ValueError("store_capacity requires a store")
        if store is not None and prepare_batch is not None:
            raise ValueError("direct store loading cannot prepare legacy batches")
        store_epoch = None
        if store is not None:
            store_epoch = (
                store.begin(store_capacity)
                if store_capacity is not None
                else store.begin_loading()
            )
        if self._session is not None:
            self._session.cancel()
        self._generation += 1
        self._session = IncrementalLoadSession(
            source,
            self._generation,
            batch_size=self.batch_size,
            queue_size=self.queue_size,
            prepare_batch=prepare_batch,
            store=store,
            store_epoch=store_epoch,
        )
        self._session.start()
        return self._session

    def cancel(self) -> None:
        """Invalidate and cancel the active source."""
        self._generation += 1
        if self._session is not None:
            self._session.cancel()
            self._session = None

    def drain(self, limit: int | None = None) -> list[LoadEvent]:
        """Drain events from only the currently selected generation."""
        if self._session is None:
            return []
        return [
            event
            for event in self._session.drain(limit)
            if event.generation == self._generation
        ]


def iter_load_events(session: IncrementalLoadSession) -> Iterator[LoadEvent]:
    """Convenience iterator for non-GUI callers that want to drain to completion."""
    while not session.finished or session._events.qsize():
        events = session.drain()
        if events:
            yield from events
        else:
            session._finished.wait(0.01)
