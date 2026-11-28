"""Compatibility façade for OEM store support helpers."""

from __future__ import annotations

import numpy as np

from ..cursor import CursorStatus
from .public_types import (
    ColumnGroupView,
    QueryRequest,
    RangeHint,
    TimeBounds,
)
from .frame_support import (
    earth_centered_frame_name,
    write_earth_fixed_chunk,
    write_series_chunk,
)
from .oem_file_capacity import (
    _CAPACITY_SCAN_CHUNK_SIZE,
    capacity_for_file,
)
from .station_profile_support import (
    station_metrics_from_profile_row,
    station_metrics_from_profile_rows,
    station_profile_events,
    station_profile_row_range,
    station_profile_row_time,
)
from .mapped_buffers import (
    _mapped_float_array,
    _mapped_buffer_id,
    _mapping_for_buffer,
    _madvise_chunk,
)
from .store_validation import (
    normalize_longitude,
    validate_elevation_threshold,
    validate_nonnegative_finite,
    validate_query_time,
    validate_time_bounds,
)
from .store_coverage import (
    coverage_for_rows,
    intersect_row_spans,
    point_segment_spans,
    ranges_intersect,
    row_spans,
    series_segment_spans,
    time_coverage,
)
from ..cursor import CursorState


def _expanded_request_bounds(request: QueryRequest) -> TimeBounds:
    bounds = validate_time_bounds(request.bounds_s)
    if request.tier in ("earth-fixed", "ground-track"):
        margin = validate_nonnegative_finite(
            request.margin_s,
            "margin_s",
        )
    elif request.tier == "station-access":
        from ..station_access import (
            ACCESS_WINDOW_MIN_MARGIN_S,
            ACCESS_WINDOW_MARGIN_FRACTION,
        )

        margin = max(
            ACCESS_WINDOW_MIN_MARGIN_S,
            ACCESS_WINDOW_MARGIN_FRACTION * (bounds[1] - bounds[0]),
        )
    else:
        return bounds
    return bounds[0] - margin, bounds[1] + margin


def _freeze_metadata(
    fields: tuple[tuple[str, object], ...],
) -> tuple[tuple[str, object], ...]:
    return tuple(
        (
            key,
            tuple(value) if isinstance(value, list) else value,
        )
        for key, value in fields
    )


_validate_time_bounds = validate_time_bounds
_normalize_longitude = normalize_longitude
_validate_nonnegative_finite = validate_nonnegative_finite
_validate_elevation_threshold = validate_elevation_threshold
_validate_query_time = validate_query_time
_ranges_intersect = ranges_intersect
_row_spans = row_spans
_intersect_row_spans = intersect_row_spans
_coverage_for_rows = coverage_for_rows
_time_coverage = time_coverage
_point_segment_spans = point_segment_spans
_series_segment_spans = series_segment_spans
_capacity_for_file = capacity_for_file
_earth_centered_frame_name = earth_centered_frame_name
_station_profile_row_time = station_profile_row_time
_station_profile_row_range = station_profile_row_range
_station_metrics_from_profile_row = station_metrics_from_profile_row
_station_metrics_from_profile_rows = station_metrics_from_profile_rows
_station_profile_events = station_profile_events
_write_series_chunk = write_series_chunk
_write_earth_fixed_chunk = write_earth_fixed_chunk


def _range_is_active(
    bounds: TimeBounds,
    hint: RangeHint | None,
) -> bool:
    if hint is None:
        return False
    plot_width = (
        max(hint.plot[1] - hint.plot[0], 1.0)
        if hint.plot is not None
        else max(hint.playback[1] - hint.playback[0], 1.0)
    )
    active_ranges = [
        hint.playback,
        (
            hint.now_s - plot_width,
            hint.now_s + plot_width,
        ),
    ]
    if hint.plot is not None:
        active_ranges.append(
            (
                hint.plot[0] - plot_width,
                hint.plot[1] + plot_width,
            )
        )
    return any(_ranges_intersect(bounds, active) for active in active_ranges)


def _unavailable_state(
    t_s: float,
    status: CursorStatus,
) -> CursorState:
    return CursorState(
        t=t_s,
        state_m=None,
        r_km=None,
        v_kms=None,
        speed=None,
        altitude=None,
        distance=None,
        status=status,
    )


def _empty_column_group(
    columns: tuple[str, ...],
) -> ColumnGroupView:
    return ColumnGroupView(
        np.empty((0, len(columns)), dtype=np.float64),
        columns,
        (),
    )
