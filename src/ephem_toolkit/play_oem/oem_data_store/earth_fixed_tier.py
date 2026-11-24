"""Earth-fixed derived-tier query implementation."""

from __future__ import annotations

from concurrent.futures import CancelledError
from threading import Event
from typing import TYPE_CHECKING

import numpy as np

from .public_types import (
    EARTH_FIXED_COLUMNS,
    EarthFixedPositions,
    QueryRequest,
    RowSpan,
    StoreQuery,
    StoreSnapshot,
    TierNotice,
    TimeCoverage,
)
from .store_support import (
    _coverage_for_rows,
    _earth_centered_frame_name,
    _intersect_row_spans,
    _point_segment_spans,
    _row_spans,
    _time_coverage,
    _validate_nonnegative_finite,
    _validate_time_bounds,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def query_earth_fixed(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    bounds_s: tuple[float, float],
    margin_s: float = 0.0,
    *,
    wait: bool = False,
    cancel_event: Event | None = None,
) -> StoreQuery[EarthFixedPositions]:
    bounds = _validate_time_bounds(bounds_s)
    store._validate_snapshot_epoch(snapshot)
    if not isinstance(wait, bool):
        raise ValueError("wait must be a boolean")
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()
    margin = _validate_nonnegative_finite(margin_s, "margin_s")
    frame_name = _earth_centered_frame_name(
        snapshot,
        "Earth-fixed positions",
    )
    if frame_name is None:
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            (),
            TimeCoverage(bounds, (), False),
        )
    if snapshot.sample_count == 0:
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            (),
            _time_coverage(snapshot, bounds),
        )

    expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
    start = int(
        np.searchsorted(
            snapshot.raw[:, 0],
            expanded_bounds[0],
            side="left",
        )
    )
    stop = int(
        np.searchsorted(
            snapshot.raw[:, 0],
            expanded_bounds[1],
            side="right",
        )
    )
    original_start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
    original_stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
    if not wait and start < stop:
        store.prefetch(
            snapshot,
            QueryRequest(
                "earth-fixed",
                bounds,
                margin_s=margin,
            ),
        )
    if start == stop:
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            (),
            _time_coverage(snapshot, bounds),
        )

    if wait:
        buffer, memo, ready = store._earth_fixed_storage(snapshot)
        store._compute_earth_fixed_range(
            snapshot,
            start,
            stop,
            buffer,
            memo,
            ready,
            cancel_event=cancel_event,
            on_chunk=lambda span: store._publish_notice(
                TierNotice(
                    snapshot.epoch,
                    "earth-fixed",
                    None,
                    None,
                    span.first,
                    span.stop,
                )
            ),
        )
    else:
        with store._lock:
            buffer = store._earth_fixed_buffer
            memo = store._earth_fixed_memo if buffer is not None else None
            ready = store._earth_fixed_ready

    if buffer is None or memo is None or ready is None:
        ready_spans = ()
        groups = ()
    else:
        with store._derived_compute_lock, store._lock:
            store._touch_chunks_locked(
                buffer,
                start,
                stop,
                expanded_bounds,
            )
            ready_spans = _row_spans(
                ready,
                start,
                stop,
                ready_value=True,
            )
            groups = tuple(
                store._make_column_group_view(
                    buffer[span.first : span.stop],
                    EARTH_FIXED_COLUMNS,
                    _point_segment_spans(
                        snapshot,
                        span.first,
                        span.stop,
                    ),
                    buffer,
                    span.first,
                    span.stop,
                )
                for span in ready_spans
            )

    in_bounds_spans = _intersect_row_spans(
        ready_spans,
        (
            (RowSpan(original_start, original_stop),)
            if original_start < original_stop
            else ()
        ),
    )
    base_coverage = _time_coverage(snapshot, bounds)
    coverage = _coverage_for_rows(
        snapshot,
        bounds,
        in_bounds_spans,
        base_coverage.complete
        and sum(span.stop - span.first for span in in_bounds_spans)
        == original_stop - original_start,
    )
    query = StoreQuery(
        snapshot.epoch,
        snapshot.revision,
        snapshot.policy_revision,
        groups,
        coverage,
    )
    store._evict_derived_buffers()
    return query
