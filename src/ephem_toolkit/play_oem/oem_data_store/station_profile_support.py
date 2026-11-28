"""Station-profile row layout and event helpers."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from ..ground_stations import GroundStation, StationMetrics
from ..station_access import CROSSING_TIME_TOLERANCE_S, _refine_peak
from .public_types import TimeBounds
from .internal_types import _StationSegmentLayout, _StoreStationCursor


def station_profile_row_time(
    layout: _StationSegmentLayout,
    index: int,
) -> float:
    """Return the timestamp for a profile row."""
    if index == layout.regular_count - 1:
        return layout.end_s
    step = (layout.end_s - layout.start_s) / (layout.regular_count - 1)
    return layout.start_s + index * step


def station_profile_row_times(
    layout: _StationSegmentLayout,
    indices: np.ndarray,
) -> np.ndarray:
    """Return timestamps for a batch of profile row indices."""
    indices = np.asarray(indices, dtype=np.intp)
    if indices.ndim != 1 or np.any(indices < 0) or np.any(
        indices >= layout.row_count
    ):
        raise ValueError("profile row indices are out of bounds")
    if layout.regular_count < 2:
        raise ValueError("regular station profile layout requires at least two rows")
    step = (layout.end_s - layout.start_s) / (layout.regular_count - 1)
    epoch_times = layout.start_s + indices * step
    epoch_times = np.asarray(epoch_times, dtype=float)
    epoch_times[indices == layout.regular_count - 1] = layout.end_s
    return epoch_times


def station_profile_row_range(
    layout: _StationSegmentLayout,
    bounds: TimeBounds,
) -> tuple[int, int]:
    """Return profile row indexes overlapping time bounds."""

    def insertion_index(
        target: float,
        *,
        right: bool,
    ) -> int:
        low = 0
        high = layout.row_count
        while low < high:
            middle = (low + high) // 2
            value = station_profile_row_time(layout, middle)
            if value < target or (right and value == target):
                low = middle + 1
            else:
                high = middle
        return low

    first = max(
        0,
        insertion_index(bounds[0], right=False) - 1,
    )
    stop = min(
        layout.row_count,
        insertion_index(bounds[1], right=True) + 1,
    )
    return first, stop


def station_metrics_from_profile_row(
    row: np.ndarray,
    minimum_elevation_deg: int,
) -> StationMetrics | None:
    """Convert one profile row to station metrics."""
    if not np.isfinite(row).all():
        return None
    return StationMetrics(
        float(row[1]),
        float(row[2]),
        float(row[3]),
        float(row[2]) >= minimum_elevation_deg,
    )


def station_metrics_from_profile_rows(
    values: np.ndarray,
    minimum_elevation_deg: int,
) -> tuple[StationMetrics | None, ...]:
    """Convert a profile row array to station metrics in batch."""
    if len(values) == 0:
        return ()
    finite = np.isfinite(values).all(axis=1)
    elevations = values[:, 2]
    return tuple(
        None
        if not bool(valid)
        else StationMetrics(
            float(values[index, 1]),
            float(elevations[index]),
            float(values[index, 3]),
            float(elevations[index]) >= minimum_elevation_deg,
        )
        for index, valid in enumerate(finite)
    )


def station_profile_events(
    values: np.ndarray,
    station: GroundStation,
    cursor: _StoreStationCursor,
    minimum_elevation_deg: int,
) -> Iterator[tuple[float, StationMetrics | None]]:
    """Yield profile samples and refined access peak events."""

    metric_rows = station_metrics_from_profile_rows(
        values,
        minimum_elevation_deg,
    )

    def sample(
        index: int,
    ) -> tuple[float, StationMetrics | None]:
        row = values[index]
        return float(row[0]), metric_rows[index]

    if len(values) == 0:
        return
    yield sample(0)
    last_peak_time: float | None = None
    valid = np.asarray(
        [metrics is not None for metrics in metric_rows],
        dtype=bool,
    )
    elevations = np.full(len(metric_rows), np.nan, dtype=float)
    elevations[valid] = np.asarray(
        [metrics.elevation_deg for metrics in metric_rows if metrics is not None],
        dtype=float,
    )
    access = np.asarray(
        [
            metrics.access
            if metrics is not None
            else False
            for metrics in metric_rows
        ],
        dtype=bool,
    )
    candidate_indices = np.flatnonzero(
        valid[1:-1]
        & ~access[1:-1]
        & valid[:-2]
        & valid[2:]
        & (elevations[1:-1] >= elevations[:-2])
        & (elevations[1:-1] >= elevations[2:])
    ) + 1

    start = 1
    for index in candidate_indices:
        for normal_index in range(start, int(index)):
            yield sample(normal_index)
        previous = sample(int(index) - 1)
        current = sample(int(index))
        following = sample(int(index) + 1)
        current_metrics = current[1]
        refined: tuple[float, StationMetrics] | None = None
        if current_metrics is not None:
            peak_time, peak_metrics = _refine_peak(
                station,
                cursor,
                previous[0],
                following[0],
            )
            peak_metrics = StationMetrics(
                peak_metrics.azimuth_deg,
                peak_metrics.elevation_deg,
                peak_metrics.slant_range_km,
                peak_metrics.elevation_deg >= minimum_elevation_deg,
            )
            if (
                peak_metrics.access
                and all(
                    abs(peak_time - sample_time) > CROSSING_TIME_TOLERANCE_S
                    for sample_time in (
                        previous[0],
                        current[0],
                        following[0],
                    )
                )
                and (
                    last_peak_time is None
                    or abs(peak_time - last_peak_time) > CROSSING_TIME_TOLERANCE_S
                )
            ):
                refined = peak_time, peak_metrics
                last_peak_time = peak_time
        if refined is not None and refined[0] < current[0]:
            yield refined
        yield current
        if refined is not None and refined[0] >= current[0]:
            yield refined
        start = int(index) + 1
    for normal_index in range(start, len(values) - 1):
        yield sample(normal_index)
    if len(values) > 1:
        yield sample(len(values) - 1)
