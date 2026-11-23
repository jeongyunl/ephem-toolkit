"""Row-span and time-coverage calculations."""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np

from ..series import SeriesGroupName
from .public_types import (
    LoadStatus,
    RowSpan,
    StoreSnapshot,
    TimeBounds,
    TimeCoverage,
)


def ranges_intersect(
    first: TimeBounds,
    second: TimeBounds,
) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def row_spans(
    ready: np.ndarray,
    start: int,
    stop: int,
    *,
    ready_value: bool,
) -> tuple[RowSpan, ...]:
    if start >= stop:
        return ()
    selected = ready[start:stop]
    transitions = np.flatnonzero(selected[1:] != selected[:-1]) + 1
    edges = np.concatenate(([0], transitions, [len(selected)]))
    return tuple(
        RowSpan(start + int(first), start + int(end))
        for first, end in zip(edges, edges[1:])
        if bool(selected[first]) is ready_value
    )


def intersect_row_spans(
    first: Sequence[RowSpan],
    second: Sequence[RowSpan],
) -> tuple[RowSpan, ...]:
    intersections = []
    left = right = 0
    while left < len(first) and right < len(second):
        start = max(first[left].first, second[right].first)
        stop = min(first[left].stop, second[right].stop)
        if start < stop:
            intersections.append(RowSpan(start, stop))
        if first[left].stop <= second[right].stop:
            left += 1
        else:
            right += 1
    return tuple(intersections)


def coverage_for_rows(
    snapshot: StoreSnapshot,
    bounds: TimeBounds,
    spans: Sequence[RowSpan],
    complete: bool,
) -> TimeCoverage:
    covered = []
    for span in spans:
        for segment_start, segment_stop in snapshot.segment_bounds:
            first = max(span.first, int(segment_start))
            stop = min(span.stop, int(segment_stop))
            if first >= stop:
                continue
            start_s = max(
                bounds[0],
                float(snapshot.raw[first, 0]),
            )
            stop_s = min(
                bounds[1],
                float(snapshot.raw[stop - 1, 0]),
            )
            if start_s <= stop_s:
                if covered and covered[-1][1] == start_s:
                    covered[-1] = (
                        covered[-1][0],
                        stop_s,
                    )
                else:
                    covered.append((start_s, stop_s))
    return TimeCoverage(bounds, tuple(covered), complete)


def time_coverage(
    snapshot: StoreSnapshot,
    bounds: TimeBounds,
) -> TimeCoverage:
    if snapshot.sample_count == 0:
        return TimeCoverage(
            bounds,
            (),
            snapshot.status is LoadStatus.COMPLETE,
        )

    covered = []
    for first, stop in snapshot.segment_bounds:
        first_index = int(first)
        stop_index = int(stop)
        if first_index >= stop_index:
            continue
        start_s = max(
            bounds[0],
            float(snapshot.raw[first_index, 0]),
        )
        stop_s = min(
            bounds[1],
            float(snapshot.raw[stop_index - 1, 0]),
        )
        if start_s <= stop_s:
            covered.append((start_s, stop_s))

    complete = snapshot.status is LoadStatus.COMPLETE or bounds[1] <= float(
        snapshot.raw[-1, 0]
    )
    return TimeCoverage(
        bounds,
        tuple(covered),
        complete,
    )


def point_segment_spans(
    snapshot: StoreSnapshot,
    start: int,
    stop: int,
) -> tuple[RowSpan, ...]:
    spans = []
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(start, int(segment_start))
        end = min(stop, int(segment_stop))
        if first < end:
            spans.append(RowSpan(first - start, end - start))
    return tuple(spans)


def series_segment_spans(
    snapshot: StoreSnapshot,
    group: SeriesGroupName,
    start: int,
    stop: int,
    stride: int,
    *,
    origin: int | None = None,
) -> tuple[RowSpan, ...]:
    if origin is None:
        origin = start
    first_view_row = math.ceil((start - origin) / stride)
    spans = []
    delta_offset = 1 if group in ("rtn", "distance-delta") else 0
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(start, int(segment_start) + delta_offset)
        end = min(stop, int(segment_stop))
        if first >= end:
            continue
        first_in_view = math.ceil((first - origin) / stride) - first_view_row
        end_in_view = math.ceil((end - origin) / stride) - first_view_row
        if first_in_view < end_in_view:
            spans.append(RowSpan(first_in_view, end_in_view))
    return tuple(spans)
