"""Station-access profile views, interval assembly, and cache policy."""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
from itertools import tee
from threading import Event
from typing import TYPE_CHECKING

from ..ground_stations import GroundStation
from ..station_access import (
    ACCESS_WINDOW_MARGIN_FRACTION,
    ACCESS_WINDOW_MIN_MARGIN_S,
    AccessInterval,
    _intervals_for_segment,
)
from .public_types import (
    STATION_PROFILE_COLUMNS,
    LoadStatus,
    LookAngleProfileView,
    QueryRequest,
    RowSpan,
    StationAccessView,
    StoreQuery,
    StoreSnapshot,
    TimeCoverage,
)
from .internal_types import _StoreStationCursor
from .store_support import (
    _earth_centered_frame_name,
    _row_spans,
    _station_profile_row_range,
    _time_coverage,
    _validate_elevation_threshold,
    _validate_time_bounds,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def query_station_access(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    station: GroundStation,
    bounds_s: tuple[float, float],
    minimum_elevation_deg: float | None = None,
    *,
    wait: bool = False,
    cancel_event: Event | None = None,
) -> StoreQuery[StationAccessView]:
    import ephem_toolkit.play_oem.oem_data_store as public_store

    bounds = _validate_time_bounds(bounds_s)
    store._validate_snapshot_epoch(snapshot)
    if not isinstance(station, GroundStation):
        raise TypeError("station must be a GroundStation")
    if not isinstance(wait, bool):
        raise ValueError("wait must be a boolean")
    threshold = (
        station.minimum_elevation_deg
        if minimum_elevation_deg is None
        else _validate_elevation_threshold(minimum_elevation_deg)
    )
    selected_station = replace(
        station,
        minimum_elevation_deg=threshold,
    )
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()

    if snapshot.sample_count == 0:
        empty = StationAccessView(selected_station, (), (), None)
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            empty,
            _time_coverage(snapshot, bounds),
        )

    frame_name = _earth_centered_frame_name(
        snapshot,
        "Station access",
    )
    if frame_name is None:
        value = StationAccessView(selected_station, (), (), None)
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            value,
            TimeCoverage(bounds, (), False),
        )

    margin = max(
        ACCESS_WINDOW_MIN_MARGIN_S,
        ACCESS_WINDOW_MARGIN_FRACTION * (bounds[1] - bounds[0]),
    )
    expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
    tier, limitation = store._station_profile_storage(
        snapshot,
        selected_station,
    )
    if limitation is not None:
        value = StationAccessView(selected_station, (), (), limitation)
        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            value,
            TimeCoverage(
                bounds,
                (),
                _time_coverage(snapshot, bounds).complete,
            ),
        )
    if not wait:
        store.prefetch(
            snapshot,
            QueryRequest(
                "station-access",
                bounds,
                station=selected_station,
                minimum_elevation_deg=float(threshold),
            ),
        )

    layout_ranges = []
    for layout in tier.layouts:
        first, stop = _station_profile_row_range(
            layout,
            expanded_bounds,
        )
        if first < stop:
            layout_ranges.append((layout, first, stop))
    with store._lock:
        for layout, first, stop in layout_ranges:
            store._touch_chunks_locked(
                tier.buffer,
                layout.base_index + first,
                layout.base_index + stop,
                expanded_bounds,
            )

    cache_key = (
        snapshot.epoch,
        snapshot.revision,
        snapshot.policy_revision,
        tier.station_key,
        bounds,
        threshold,
    )
    with store._lock:
        cached_intervals = store._station_interval_cache.get(cache_key)

    if wait:
        store._compute_station_profile_ranges(
            snapshot,
            selected_station,
            tier,
            frame_name,
            layout_ranges,
            cancel_event=cancel_event,
        )

    profile_views = []
    intervals = []
    coverage_spans = []
    cursor = _StoreStationCursor(
        store,
        snapshot,
        store._interpolation_policy,
    )
    ready_values = []
    if tier.ready is not None:
        with store._derived_compute_lock, store._lock:
            for layout, first, stop in layout_ranges:
                first_row = layout.base_index + first
                stop_row = layout.base_index + stop
                ready_spans = _row_spans(
                    tier.ready,
                    first_row,
                    stop_row,
                    ready_value=True,
                )
                for span in ready_spans:
                    values = tier.buffer[span.first : span.stop]
                    profile_views.append(
                        LookAngleProfileView(
                            store._make_column_group_view(
                                values,
                                STATION_PROFILE_COLUMNS,
                                (RowSpan(0, len(values)),),
                                tier.buffer,
                                span.first,
                                span.stop,
                            )
                        )
                    )
                    ready_values.append(
                        (
                            layout,
                            span.first - layout.base_index,
                            span.stop - layout.base_index,
                            values,
                        )
                    )

    for layout, first, stop, values in ready_values:
        first_time = float(values[0, 0])
        stop_time = float(values[-1, 0])
        covered_start = max(bounds[0], first_time)
        covered_stop = min(bounds[1], stop_time)
        if covered_start <= covered_stop:
            coverage_spans.append((covered_start, covered_stop))
        if len(values) < 2 or cached_intervals is not None:
            continue
        events = public_store._station_profile_events(
            values,
            selected_station,
            cursor,
            frame_name,
            threshold,
        )
        timed_events, metric_events = tee(events)
        intervals.extend(
            _intervals_for_segment(
                selected_station,
                cursor,
                frame_name,
                (event[0] for event in timed_events),
                (event[1] for event in metric_events),
                starts_at_coverage=first == 0,
                ends_at_coverage=stop == layout.row_count,
                starts_after_gap=layout.raw_start > 0,
                ends_before_gap=layout.raw_stop < snapshot.sample_count,
            )
        )

    base_coverage = _time_coverage(snapshot, bounds)
    if tier.ready is None:
        requested_rows_ready = not layout_ranges
    else:
        with store._derived_compute_lock:
            requested_rows_ready = all(
                sum(
                    span.stop - span.first
                    for span in _row_spans(
                        tier.ready,
                        layout.base_index + first,
                        layout.base_index + stop,
                        ready_value=True,
                    )
                )
                == stop - first
                for layout, first, stop in layout_ranges
            )
    coverage = TimeCoverage(
        bounds,
        tuple(coverage_spans),
        base_coverage.complete and requested_rows_ready,
    )
    value = StationAccessView(
        selected_station,
        tuple(profile_views),
        cached_intervals if cached_intervals is not None else tuple(intervals),
        (
            "An access interval reaches an OEM segment gap; "
            "its crossing is unavailable."
            if any(
                interval.limited_by_gap_at_start or interval.limited_by_gap_at_end
                for interval in (
                    cached_intervals if cached_intervals is not None else intervals
                )
            )
            else None
        ),
    )
    result = StoreQuery(
        snapshot.epoch,
        snapshot.revision,
        snapshot.policy_revision,
        value,
        coverage,
    )
    if requested_rows_ready and snapshot.status is LoadStatus.COMPLETE:
        with store._lock:
            store._station_interval_cache[cache_key] = value.intervals
            if len(store._station_interval_cache) > 128:
                oldest = next(iter(store._station_interval_cache))
                store._station_interval_cache.pop(oldest)
    store._evict_derived_buffers()
    return result
