"""Shared chunk-range execution for store-owned derived tiers."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import CancelledError
from threading import Event

import numpy as np

from ..chunk_memo import ChunkMemo
from .public_types import LoadStatus, RowSpan, StoreSnapshot


def _row_spans(
    ready: np.ndarray,
    start: int,
    stop: int,
) -> tuple[RowSpan, ...]:
    if start >= stop:
        return ()
    selected = ready[start:stop]
    transitions = np.flatnonzero(selected[1:] != selected[:-1]) + 1
    edges = np.concatenate(([0], transitions, [len(selected)]))
    return tuple(
        RowSpan(start + int(first), start + int(end))
        for first, end in zip(edges, edges[1:])
        if not bool(selected[first])
    )


def compute_missing_chunk_ranges(
    snapshot: StoreSnapshot,
    ready: np.ndarray,
    start: int,
    stop: int,
    memo: ChunkMemo[int, RowSpan],
    chunk_size: int,
    write_span: Callable[[RowSpan], None],
    *,
    policy_revision: int = 0,
    cancel_event: Event | None = None,
    on_chunk: Callable[[RowSpan], None] | None = None,
) -> None:
    """Compute missing spans inside chunk-aligned ranges."""
    first_chunk = start // chunk_size
    last_chunk = (stop - 1) // chunk_size
    for chunk_index in range(first_chunk, last_chunk + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        chunk_start = chunk_index * chunk_size
        chunk_stop = min(chunk_start + chunk_size, snapshot.sample_count)
        requested_start = max(start, chunk_start)
        requested_stop = min(stop, chunk_stop)
        missing_spans = _row_spans(
            ready,
            requested_start,
            requested_stop,
        )
        if not missing_spans:
            memo.record_hit()
            continue
        memo.discard(chunk_index)
        tentative = (
            snapshot.status is LoadStatus.LOADING
            and chunk_stop < chunk_start + chunk_size
        )

        def compute() -> RowSpan:
            for span in missing_spans:
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                write_span(span)
                ready[span.first : span.stop] = True
                if on_chunk is not None:
                    on_chunk(span)
            return RowSpan(requested_start, requested_stop)

        memo.get_or_compute(
            chunk_index,
            compute,
            epoch=snapshot.epoch,
            policy_revision=policy_revision,
            tentative=tentative,
            cancel_event=cancel_event,
        )
