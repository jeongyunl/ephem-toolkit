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
)


class LoadEventKind(str, Enum):
    """Kinds of messages a load session delivers to its owner."""

    STARTED = "started"
    BATCH = "batch"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class LoadEvent:
    """Immutable event tagged with the file-selection generation that produced it."""

    generation: int
    kind: LoadEventKind
    loaded_state_count: int
    batch: OemStateBatch | None = None
    prepared: object | None = None
    completion: OemStreamComplete | None = None
    error: OemStreamError | None = None


class _Cancelled(Exception):
    """Internal signal used when a session's bounded event queue is canceled."""


class IncrementalLoadSession:
    """Read a file off-thread and expose bounded events for GUI-thread polling."""

    def __init__(
        self,
        source: str | Path,
        generation: int,
        *,
        batch_size: int = 512,
        batch_interval_s: float = 0.1,
        queue_size: int = 2,
        prepare_batch: Callable[[OemStateBatch], object] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        if batch_interval_s <= 0.0:
            raise ValueError("batch_interval_s must be positive")
        self.source = Path(source)
        self.generation = generation
        self.batch_size = batch_size
        self.batch_interval_s = batch_interval_s
        self._prepare_batch = prepare_batch
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

        try:
            completion = read_oem_batches(
                self.source,
                batch_size=self.batch_size,
                batch_interval_s=self.batch_interval_s,
                on_batch=deliver_batch,
                cancel_event=self._cancelled,
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
    ) -> IncrementalLoadSession:
        """Cancel the prior source and start a new monotonically tagged generation."""
        if self._session is not None:
            self._session.cancel()
        self._generation += 1
        self._session = IncrementalLoadSession(
            source,
            self._generation,
            batch_size=self.batch_size,
            queue_size=self.queue_size,
            prepare_batch=prepare_batch,
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
