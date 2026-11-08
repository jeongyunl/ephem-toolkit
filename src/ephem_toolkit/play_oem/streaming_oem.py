"""Background streaming reader for playback-oriented OEM loading."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
from typing import Any, Union

import ephem_toolkit.core.ccsds.oem as ccsds_oem
import ephem_toolkit.core.ccsds.odm as odm
import numpy as np

from .oem_data_store import OemDataStore, RawAppendNotice, RawReservation


@dataclass(frozen=True)
class OemStreamComplete:
    """Whole-file records available after EOF validation succeeds."""

    header: tuple[tuple[str, Any], ...]
    meta: tuple[tuple[str, Any], ...]
    state_count: int


OemStreamEvent = Union[ccsds_oem.OemStateBatch, OemStreamComplete]


class OemStreamError(Exception):
    """Failure raised by the background OEM reader."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(str(cause))
        self.cause = cause


class _Cancelled(Exception):
    """Internal signal used to stop a producer when its consumer is gone."""


class _StoreRowSink:
    def __init__(
        self,
        store: OemDataStore,
        epoch: int,
        batch_size: int,
        batch_interval_s: float,
        on_append: Callable[[RawAppendNotice], None],
        cancel_event: Event,
    ) -> None:
        self.store = store
        self.epoch = epoch
        self.batch_size = batch_size
        self.batch_interval_s = batch_interval_s
        self.on_append = on_append
        self.cancel_event = cancel_event
        self.reservation: RawReservation | None = None
        self.count = 0
        self.total = 0
        self.last_flush = monotonic()

    def reserve_row(self, timestamp: float, segment_id: int) -> np.ndarray:
        if self.cancel_event.is_set():
            raise _Cancelled
        if self.reservation is None:
            self.reservation = self.store.reserve(self.batch_size, epoch=self.epoch)
        self.reservation.segment_ids[self.count] = segment_id
        return self.reservation.raw[self.count]

    def finish_row(self) -> None:
        assert self.reservation is not None
        self.count += 1
        if (
            self.count == len(self.reservation.raw)
            or monotonic() - self.last_flush >= self.batch_interval_s
        ):
            self.flush()

    def flush(self) -> None:
        if self.cancel_event.is_set():
            raise _Cancelled
        if self.reservation is None:
            return
        notice = self.store.commit(self.reservation, self.count)
        self.reservation = None
        self.total += self.count
        self.count = 0
        self.last_flush = monotonic()
        self.on_append(notice)
        if self.cancel_event.is_set():
            raise _Cancelled

    def close(self) -> None:
        if self.reservation is not None:
            self.store.discard_if_active(self.reservation)
            self.reservation = None


def read_oem_into_store(
    source: str | Path,
    store: OemDataStore,
    *,
    batch_size: int,
    batch_interval_s: float = 0.1,
    on_append: Callable[[RawAppendNotice], None],
    cancel_event: Event,
    expected_epoch: int | None = None,
) -> OemStreamComplete:
    """Parse directly into a begun raw store, validating through EOF.

    Previously committed prefixes remain provisional on failure or cancellation.
    The owner must invalidate the store epoch when discarding or replacing the load.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if batch_interval_s <= 0:
        raise ValueError("batch_interval_s must be positive")
    initial = store.snapshot()
    if expected_epoch is not None and initial.epoch != expected_epoch:
        raise RuntimeError("store epoch has changed")
    if initial.sample_count:
        raise ValueError("direct ingestion requires an empty store epoch")
    sink = _StoreRowSink(
        store, initial.epoch, batch_size, batch_interval_s, on_append, cancel_event
    )
    try:
        header, meta, _, _, _ = ccsds_oem.CcsdsOem._read_oem_impl(
            source,
            state_row_sink=sink,
            retain_states=False,
            retain_comments=False,
            retain_covariances=False,
        )
        sink.flush()
        odm.validate_odm_context(
            str(meta.get("CENTER_NAME", "")),
            str(meta.get("REF_FRAME", "")),
            str(meta.get("TIME_SYSTEM", "")),
            require_center=False,
        )
        if cancel_event.is_set():
            raise _Cancelled
        completion = OemStreamComplete(
            tuple(header.items()), tuple(meta.items()), sink.total
        )
        store.mark_complete(sink.epoch, completion.header, completion.meta)
        return completion
    except _Cancelled:
        store.cancel_if_epoch(sink.epoch)
        raise
    except Exception as error:
        store.mark_failed(sink.epoch, error)
        raise
    finally:
        sink.close()


def read_oem_batches(
    source: str | Path,
    *,
    batch_size: int,
    batch_interval_s: float = 0.1,
    on_batch: Callable[[ccsds_oem.OemStateBatch], None],
    cancel_event: Event,
) -> OemStreamComplete:
    """Parse a file synchronously, forwarding batches and validating through EOF."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    state_count = 0

    def deliver(batch: ccsds_oem.OemStateBatch) -> None:
        nonlocal state_count
        if cancel_event.is_set():
            raise _Cancelled
        state_count += len(batch.states)
        on_batch(batch)
        if cancel_event.is_set():
            raise _Cancelled

    header, meta, _, _, _ = ccsds_oem.CcsdsOem._read_oem_impl(
        source,
        state_batch_size=batch_size,
        state_batch_interval_s=batch_interval_s,
        on_state_batch=deliver,
        retain_states=False,
        retain_comments=False,
        retain_covariances=False,
    )
    if cancel_event.is_set():
        raise _Cancelled
    odm.validate_odm_context(
        str(meta.get("CENTER_NAME", "")),
        str(meta.get("REF_FRAME", "")),
        str(meta.get("TIME_SYSTEM", "")),
        require_center=False,
    )
    return OemStreamComplete(
        tuple(header.items()),
        tuple(meta.items()),
        state_count,
    )


def iter_oem_events(
    source: str | Path,
    *,
    batch_size: int = 4096,
    batch_interval_s: float = 0.1,
    queue_size: int = 2,
    cancel_event: Event | None = None,
) -> Iterator[OemStreamEvent]:
    """Yield bounded parsed batches from a file while a worker validates the rest.

    The queue applies back-pressure so parsing cannot get arbitrarily far ahead of the
    consumer. Closing the iterator cancels the worker at its next batch boundary.
    A final :class:`OemStreamComplete` event is emitted only after EOF checks and ODM
    context validation pass.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if queue_size < 1:
        raise ValueError("queue_size must be positive")

    events: Queue[OemStreamEvent | Exception | None] = Queue(maxsize=queue_size)
    cancelled = cancel_event or Event()
    def publish(event: OemStreamEvent | Exception | None) -> None:
        while not cancelled.is_set():
            try:
                events.put(event, timeout=0.1)
                return
            except Full:
                continue
        raise _Cancelled

    def produce() -> None:
        def publish_batch(batch: ccsds_oem.OemStateBatch) -> None:
            publish(batch)

        try:
            publish(
                read_oem_batches(
                    source,
                    batch_size=batch_size,
                    batch_interval_s=batch_interval_s,
                    on_batch=publish_batch,
                    cancel_event=cancelled,
                )
            )
        except _Cancelled:
            pass
        except Exception as error:
            try:
                publish(OemStreamError(error))
            except _Cancelled:
                pass
        finally:
            try:
                publish(None)
            except _Cancelled:
                pass

    worker = Thread(target=produce, name="play-oem-reader", daemon=True)
    worker.start()
    try:
        while True:
            if cancelled.is_set():
                return
            try:
                event = events.get(timeout=0.1)
            except Empty:
                if not worker.is_alive():
                    return
                continue
            if event is None:
                return
            if isinstance(event, OemStreamError):
                raise event from event.cause
            yield event
    finally:
        if cancel_event is None:
            cancelled.set()
