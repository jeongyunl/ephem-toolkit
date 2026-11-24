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


def station_profile_events(
    values: np.ndarray,
    station: GroundStation,
    cursor: _StoreStationCursor,
    minimum_elevation_deg: int,
) -> Iterator[tuple[float, StationMetrics | None]]:
    """Yield profile samples and refined access peak events."""

    def sample(
        index: int,
    ) -> tuple[float, StationMetrics | None]:
        row = values[index]
        return float(row[0]), station_metrics_from_profile_row(
            row,
            minimum_elevation_deg,
        )

    if len(values) == 0:
        return
    yield sample(0)
    last_peak_time: float | None = None
    for index in range(1, len(values) - 1):
        previous = sample(index - 1)
        current = sample(index)
        following = sample(index + 1)
        current_metrics = current[1]
        previous_metrics = previous[1]
        following_metrics = following[1]
        refined: tuple[float, StationMetrics] | None = None
        if (
            current_metrics is not None
            and not current_metrics.access
            and previous_metrics is not None
            and following_metrics is not None
            and current_metrics.elevation_deg >= previous_metrics.elevation_deg
            and current_metrics.elevation_deg >= following_metrics.elevation_deg
        ):
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
    if len(values) > 1:
        yield sample(len(values) - 1)
