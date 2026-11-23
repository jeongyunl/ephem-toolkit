"""Raw OEM reservation and append lifecycle helpers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .public_types import LoadStatus, RawAppendNotice, RawReservation

if TYPE_CHECKING:
    from .data_store import OemDataStore


def check_reservation(store: OemDataStore, reservation: RawReservation) -> None:
    if (
        store._reservation is not reservation
        or reservation.epoch != store._epoch
        or reservation.first_index != store._sample_count
    ):
        raise RuntimeError("reservation is stale or does not belong to this store")


def reserve(
    store: OemDataStore,
    max_rows: int,
    *,
    epoch: int | None = None,
) -> RawReservation:
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer")
    with store._lock:
        if epoch is not None and epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if store._raw is None or store._segment_ids is None:
            raise RuntimeError("store has no active epoch")
        if store._status is not LoadStatus.LOADING:
            raise RuntimeError(f"store is not loading: {store._status.value}")
        if store._reservation is not None:
            raise RuntimeError("a raw reservation is already active")
        stop = min(store._sample_count + max_rows, len(store._raw))
        if stop == store._sample_count:
            raise OverflowError("raw storage capacity exceeded")
        reservation = RawReservation(
            store._epoch,
            store._sample_count,
            store._raw[store._sample_count : stop],
            store._segment_ids[store._sample_count : stop],
        )
        store._reservation = reservation
        return reservation


def abort(store: OemDataStore, reservation: RawReservation) -> None:
    with store._lock:
        check_reservation(store, reservation)
        if store._validating:
            raise RuntimeError("reservation validation is in progress")
        reservation._close()
        store._reservation = None


def discard_if_active(
    store: OemDataStore,
    reservation: RawReservation,
) -> bool:
    with store._lock:
        if store._reservation is not reservation:
            return False
        if store._validating:
            raise RuntimeError("reservation validation is in progress")
        reservation._close()
        store._reservation = None
        return True


def commit(
    store: OemDataStore,
    reservation: RawReservation,
    count: int,
) -> RawAppendNotice:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    with store._lock:
        check_reservation(store, reservation)
        if store._validating:
            raise RuntimeError("reservation validation is in progress")
        if count > len(reservation.raw):
            raise ValueError("count exceeds reservation capacity")
        store._validating = True
        previous_time = (
            float(store._raw[store._sample_count - 1, 0])
            if store._sample_count and store._raw is not None
            else None
        )
        previous_segment = (
            int(store._segment_ids[store._sample_count - 1])
            if store._sample_count and store._segment_ids is not None
            else None
        )
    try:
        boundaries: list[tuple[int, int]] = []
        max_gap = 0.0
        for index in range(count):
            row = reservation.raw[index]
            segment = int(reservation.segment_ids[index])
            timestamp = float(row[0])
            if not all(math.isfinite(float(value)) for value in row):
                raise ValueError("timestamps and states must be finite")
            if previous_time is not None and timestamp <= previous_time:
                raise ValueError("timestamps must be strictly increasing")
            if previous_segment is not None and segment < previous_segment:
                raise ValueError("segment IDs must be non-decreasing")
            if segment != previous_segment:
                boundaries.append((reservation.first_index + index, segment))
            elif previous_time is not None:
                max_gap = max(max_gap, timestamp - previous_time)
            previous_time = timestamp
            previous_segment = segment
        with store._lock:
            check_reservation(store, reservation)
            if store._sample_times is None:
                raise RuntimeError("store timestamps are not allocated")
            stop = store._sample_count + count
            for start, segment in boundaries:
                if store._segment_bounds:
                    old_segment, old_start, _ = store._segment_bounds[-1]
                    store._segment_bounds[-1] = (old_segment, old_start, start)
                store._segment_bounds.append((segment, start, stop))
            if store._segment_bounds:
                segment, start, _ = store._segment_bounds[-1]
                store._segment_bounds[-1] = (segment, start, stop)
            store._max_gap_s = max(store._max_gap_s, max_gap)
            store._sample_count = stop
            store._sample_times._publish_validated_count(stop)
            store._revision += 1
            store._clear_station_tiers_locked()
            store._ground_track_cache.clear()
            notice = RawAppendNotice(
                store._epoch,
                store._revision,
                reservation.first_index,
                stop,
                (
                    float(reservation.raw[0, 0]),
                    float(reservation.raw[count - 1, 0]),
                ),
            )
            reservation._close()
            store._reservation = None
            store._validating = False
            return notice
    finally:
        with store._lock:
            if store._reservation is reservation:
                store._validating = False
