"""Raw OEM epoch allocation, reset, and terminal lifecycle transitions."""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from ..clock import SampleTimes
from .public_types import LoadStatus

if TYPE_CHECKING:
    from .data_store import OemDataStore


def begin(store: OemDataStore, capacity: int) -> int:
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive integer")
    raw = np.empty((capacity, 7), dtype=np.float64)
    segment_ids = np.empty(capacity, dtype=np.int64)
    with store._lock:
        store._reset_locked()
        store._raw = raw
        store._segment_ids = segment_ids
        timestamp_view = raw[:, 0].view()
        timestamp_view.setflags(write=False)
        store._sample_times = SampleTimes(timestamp_view, 0)
        store._status = LoadStatus.LOADING
        return store._epoch


def begin_loading(store: OemDataStore) -> int:
    with store._lock:
        store._reset_locked()
        store._status = LoadStatus.LOADING
        return store._epoch


def allocate_if_epoch(
    store: OemDataStore,
    epoch: int,
    capacity: int,
) -> bool:
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive integer")
    with store._lock:
        if (
            epoch != store._epoch
            or store._status is not LoadStatus.LOADING
            or store._raw is not None
        ):
            return False
    raw = np.empty((capacity, 7), dtype=np.float64)
    segment_ids = np.empty(capacity, dtype=np.int64)
    with store._lock:
        if (
            epoch != store._epoch
            or store._status is not LoadStatus.LOADING
            or store._raw is not None
        ):
            return False
        store._raw = raw
        store._segment_ids = segment_ids
        timestamp_view = raw[:, 0].view()
        timestamp_view.setflags(write=False)
        store._sample_times = SampleTimes(timestamp_view, 0)
        return True


def clear_if_epoch(store: OemDataStore, epoch: int) -> bool:
    with store._lock:
        if epoch != store._epoch:
            return False
        store._reset_locked()
        return True


def cancel_if_epoch(store: OemDataStore, epoch: int) -> bool:
    with store._lock:
        if epoch != store._epoch or store._status is not LoadStatus.LOADING:
            return False
        if store._reservation is not None:
            store._reservation._close()
            store._reservation = None
        store._validating = False
        store._status = LoadStatus.CANCELLED
        store._failure = None
        store._revision += 1
        return True


def mark_complete(
    store: OemDataStore,
    epoch: int,
    header: tuple[tuple[str, object], ...],
    meta: tuple[tuple[str, object], ...],
) -> None:
    from .store_support import _freeze_metadata

    with store._lock:
        if epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if store._status is not LoadStatus.LOADING:
            raise RuntimeError("store is not loading")
        if store._reservation is not None:
            raise RuntimeError("cannot complete with an active reservation")
        store._header = _freeze_metadata(header)
        store._meta = _freeze_metadata(meta)
        store._failure = None
        store._status = LoadStatus.COMPLETE
        store._revision += 1


def mark_failed(
    store: OemDataStore,
    epoch: int,
    failure: Exception,
) -> bool:
    with store._lock:
        if epoch != store._epoch or store._status is not LoadStatus.LOADING:
            return False
        if store._reservation is not None:
            store._reservation._close()
            store._reservation = None
        store._validating = False
        store._status = LoadStatus.FAILED
        store._failure = str(failure)
        store._revision += 1
        return True


def reset_locked(store: OemDataStore) -> None:
    store._cancel_scheduled_work()
    if store._reservation is not None:
        store._reservation._close()
    for memo in store._series_memos.values():
        memo.clear()
    store._earth_fixed_memo.clear()
    store._series_buffers.clear()
    store._series_ready.clear()
    store._earth_fixed_buffer = None
    store._earth_fixed_ready = None
    store._ground_track_cache.clear()
    store._clear_station_tiers_locked()
    store._footprint_cache.clear()
    store._chunk_access_order.clear()
    store._chunk_ranges.clear()
    store._epoch += 1
    store._revision = 0
    store._policy_revision = 0
    store._sample_count = 0
    store._raw = None
    store._segment_ids = None
    store._sample_times = None
    store._segment_bounds = []
    store._max_gap_s = 0.0
    store._status = LoadStatus.EMPTY
    store._header = ()
    store._meta = ()
    store._failure = None
    store._reservation = None
    store._validating = False
