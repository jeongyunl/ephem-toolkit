"""Series-tier storage, range assembly, and memo lifecycle."""

from __future__ import annotations

import math
from collections.abc import Sequence
from concurrent.futures import CancelledError, Future
from threading import Event
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

from ..chunk_memo import ChunkMemo, ChunkState
from ..series import SERIES_GROUPS, SeriesGroupName, _SERIES_COLUMNS
from .public_types import (
    ColumnGroupView,
    RowSpan,
    SeriesGroups,
    StoreQuery,
    StoreSnapshot,
    TierNotice,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def series_storage(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    group: SeriesGroupName,
) -> tuple[np.ndarray, ChunkMemo[int, RowSpan], np.ndarray]:
    from .mapped_buffers import _mapped_float_array

    with store._lock:
        if snapshot.epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if store._raw is None:
            raise RuntimeError("store has no active epoch")
        buffer = store._series_buffers.get(group)
        if buffer is None:
            buffer = _mapped_float_array((len(store._raw), len(_SERIES_COLUMNS[group])))
            store._series_buffers[group] = buffer
            store._series_ready[group] = np.zeros(
                len(store._raw),
                dtype=bool,
            )
        memo = store._series_memos.get(group)
        if memo is None:
            memo = ChunkMemo()
            store._series_memos[group] = memo
        return buffer, memo, store._series_ready[group]


def query_series(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    bounds_s: tuple[float, float],
    groups: Sequence[SeriesGroupName] | None = None,
    max_samples: int | None = None,
    *,
    wait: bool = False,
    cancel_event: Event | None = None,
) -> StoreQuery[SeriesGroups]:
    import ephem_toolkit.play_oem.oem_data_store as public_store
    from .store_support import (
        _coverage_for_rows,
        _intersect_row_spans,
        _row_spans,
        _series_segment_spans,
        _time_coverage,
        _validate_time_bounds,
    )

    bounds = _validate_time_bounds(bounds_s)
    store._validate_snapshot_epoch(snapshot)
    selected_groups = (
        tuple(SERIES_GROUPS) if groups is None else tuple(dict.fromkeys(groups))
    )
    unknown_groups = set(selected_groups).difference(SERIES_GROUPS)
    if unknown_groups:
        raise ValueError(f"unsupported series groups: {sorted(unknown_groups)}")
    if not isinstance(wait, bool):
        raise ValueError("wait must be a boolean")
    if max_samples is not None and (
        isinstance(max_samples, bool)
        or not isinstance(max_samples, int)
        or max_samples < 1
    ):
        raise ValueError("max_samples must be a positive integer")
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()

    if snapshot.sample_count == 0:
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            MappingProxyType({group: () for group in selected_groups}),
            _time_coverage(snapshot, bounds),
        )

    start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
    stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
    if not wait and start < stop and selected_groups:
        store.prefetch(
            snapshot,
            public_store.QueryRequest(
                "series",
                bounds,
                series_groups=selected_groups,
                max_samples=max_samples,
            ),
        )

    result: dict[SeriesGroupName, tuple[ColumnGroupView, ...]] = {}
    ready_by_group: list[tuple[RowSpan, ...]] = []
    series_futures: list[Future[None]] = []
    wait_states: dict[
        SeriesGroupName,
        tuple[np.ndarray, ChunkMemo[int, RowSpan], np.ndarray],
    ] = {}
    for group in selected_groups:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        if start == stop:
            continue
        if wait:
            buffer, memo, ready = series_storage(store, snapshot, group)
            wait_states[group] = (buffer, memo, ready)
            needs_computation = bool(np.any(~ready[start:stop]))
            if not needs_computation:
                first_chunk = start // public_store.DERIVED_CHUNK_SIZE
                last_chunk = (stop - 1) // public_store.DERIVED_CHUNK_SIZE
                for chunk_index in range(first_chunk, last_chunk + 1):
                    chunk_state = memo.state(
                        chunk_index,
                        epoch=snapshot.epoch,
                        policy_revision=0,
                    )
                    if chunk_state is ChunkState.TENTATIVE:
                        needs_computation = True
                        break
                    if chunk_state is ChunkState.COMPLETE:
                        memo.record_hit()
            if needs_computation:
                series_futures.append(
                    store._series_executor.submit(
                        store._compute_series_range,
                        snapshot,
                        group,
                        start,
                        stop,
                        buffer,
                        memo,
                        ready,
                        cancel_event=cancel_event,
                        on_chunk=lambda span, group_name=group: store._publish_notice(
                            TierNotice(
                                snapshot.epoch,
                                "series",
                                group_name,
                                None,
                                span.first,
                                span.stop,
                            )
                        ),
                    )
                )

    for future in series_futures:
        future.result()

    for group in selected_groups:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        if start == stop:
            result[group] = ()
            ready_by_group.append(())
            continue
        if wait:
            buffer, memo, ready = wait_states[group]
        else:
            with store._lock:
                buffer = store._series_buffers.get(group)
                memo = store._series_memos.get(group)
                ready = store._series_ready.get(group)
        if buffer is None or memo is None or ready is None:
            ready_spans = ()
            group_data_views = ()
        else:
            stride = 1
            row_count = stop - start
            if max_samples is not None and row_count > max_samples:
                stride = math.ceil(row_count / max_samples)
            with store._derived_compute_lock, store._lock:
                store._touch_chunks_locked(buffer, start, stop, bounds)
                ready_spans = _row_spans(
                    ready,
                    start,
                    stop,
                    ready_value=True,
                )
                group_data_views = tuple(
                    store._make_column_group_view(
                        buffer[
                            start
                            + math.ceil((span.first - start) / stride)
                            * stride : span.stop : stride
                        ],
                        _SERIES_COLUMNS[group],
                        _series_segment_spans(
                            snapshot,
                            group,
                            start + math.ceil((span.first - start) / stride) * stride,
                            span.stop,
                            stride,
                            origin=start,
                        ),
                        buffer,
                        span.first,
                        span.stop,
                    )
                    for span in ready_spans
                    if start + math.ceil((span.first - start) / stride) * stride
                    < span.stop
                )
        ready_by_group.append(ready_spans)
        result[group] = group_data_views

    base_coverage = _time_coverage(snapshot, bounds)
    if selected_groups:
        common_spans = ready_by_group[0]
        for spans in ready_by_group[1:]:
            common_spans = _intersect_row_spans(common_spans, spans)
        coverage = _coverage_for_rows(
            snapshot,
            bounds,
            common_spans,
            base_coverage.complete
            and sum(span.stop - span.first for span in common_spans) == stop - start,
        )
    else:
        coverage = base_coverage

    query = StoreQuery[SeriesGroups](
        snapshot.epoch,
        snapshot.revision,
        snapshot.policy_revision,
        MappingProxyType(result),
        coverage,
    )
    store._evict_derived_buffers()
    return query
