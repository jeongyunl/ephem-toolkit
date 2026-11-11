"""Background streaming reader for playback-oriented OEM loading."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any

import ephem_toolkit.core.ccsds.oem as ccsds_oem
import ephem_toolkit.core.ccsds.odm as odm
import numpy as np

from .ground_track import normalize_frame_name
from .oem_data_store import OemDataStore, RawAppendNotice, RawReservation


@dataclass(frozen=True)
class OemStreamComplete:
    """Whole-file records available after EOF validation succeeds."""

    header: tuple[tuple[str, Any], ...]
    meta: tuple[tuple[str, Any], ...]
    state_count: int

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
    on_segment_metadata: Callable[[int, dict[str, Any]], None] | None = None,
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

    def publish_segment_metadata(
        segment_id: int, segment_meta: dict[str, Any]
    ) -> None:
        ref_frame = segment_meta.get("REF_FRAME")
        if isinstance(ref_frame, str):
            segment_meta["REF_FRAME"] = normalize_frame_name(ref_frame)
        time_system = str(segment_meta.get("TIME_SYSTEM", "")).strip().upper()
        if time_system != "UTC":
            displayed_time_system = time_system or "unspecified"
            raise ValueError(
                "play-oem currently supports OEM TIME_SYSTEM = UTC only; "
                f"found {displayed_time_system!r}."
            )
        if on_segment_metadata is not None:
            on_segment_metadata(segment_id, segment_meta)

    try:
        with Path(source).open("r", encoding="utf-8") as source_file:
            parsed = ccsds_oem.CcsdsOem._read_oem_impl(
                source_file,
                include_segment_ids=True,
                on_segment_metadata=publish_segment_metadata,
                state_row_sink=sink,
                retain_states=False,
                retain_comments=False,
                retain_covariances=False,
            )
        header, meta = parsed[0], parsed[1]
        sink.flush()
        ref_frame = meta.get("REF_FRAME")
        if isinstance(ref_frame, str):
            meta["REF_FRAME"] = normalize_frame_name(ref_frame)
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
