"""Ground-station access metrics and OEM-bounded pass preparation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from .cursor import CursorStatus, OemCursor
from .ground_stations import (
    GroundStation,
    StationMetrics,
    station_metrics,
    station_metrics_from_ecef,
)
from .ground_track import (
    EarthFixedPositionCache,
    GroundTrackPreparationError,
    GroundTrackSource,
)

MAX_ACCESS_SAMPLE_STEP_S = 30.0
MAX_SOURCE_SAMPLE_GAP_S = 300.0
CROSSING_TIME_TOLERANCE_S = 0.5
MAX_ACCESS_SAMPLES = 1_000_000


@dataclass(frozen=True)
class AccessInterval:
    """A station access interval clipped to OEM coverage."""

    start_s: float
    end_s: float
    peak_elevation_deg: float
    peak_time_s: float
    minimum_range_km: float
    minimum_range_time_s: float
    clipped_at_start: bool = False
    clipped_at_end: bool = False
    limited_by_gap_at_start: bool = False
    limited_by_gap_at_end: bool = False


@dataclass(frozen=True)
class StationAccess:
    """Prepared access history and any prediction limitation for a station."""

    station: GroundStation
    intervals: tuple[AccessInterval, ...]
    limitation: str | None = None


def current_station_metrics(
    station: GroundStation,
    cursor: OemCursor,
    time_s: float,
    source: GroundTrackSource,
    position_cache: EarthFixedPositionCache | None = None,
) -> StationMetrics | None:
    """Resolve current metrics without extrapolating or crossing an OEM gap."""
    if source.center_name.strip().upper() not in ("EARTH", "399"):
        raise GroundTrackPreparationError(
            f"Ground Station Access requires an Earth-centered OEM; found {source.center_name!r}"
        )
    if position_cache is None:
        position_cache = EarthFixedPositionCache()
    state = cursor.lookup(time_s)
    if state.status not in (CursorStatus.EXACT_SAMPLE, CursorStatus.INTERPOLATED):
        return None
    if state.state_m is None:
        return None
    return _metrics_for_state(
        station, state.state_m, source, source.frame_name, time_s, position_cache
    )


def prepare_station_access(
    source: GroundTrackSource,
    cursor: OemCursor,
    station: GroundStation,
    position_cache: EarthFixedPositionCache | None = None,
) -> StationAccess:
    """Prepare access intervals on a uniform grid with refined threshold crossings.

    Each OEM segment is evaluated on a uniform grid with at most 30 seconds
    between epochs. Sampled local maxima are refined to detect sub-step passes.
    Source gaps over five minutes are considered too sparse for a reliable
    prediction and suppress interval output for that station.
    """
    center = source.center_name.strip().upper()
    if center not in ("EARTH", "399"):
        raise GroundTrackPreparationError(
            f"Ground Station Access requires an Earth-centered OEM; found {source.center_name!r}"
        )
    timestamps = np.asarray(source.timestamps_s, dtype=float)
    states = np.asarray(source.states_m, dtype=float)
    segments = np.asarray(source.segment_ids, dtype=int)
    if (
        timestamps.ndim != 1
        or timestamps.size == 0
        or states.shape != (timestamps.size, 6)
        or segments.shape != timestamps.shape
        or not np.isfinite(timestamps).all()
        or not np.isfinite(states).all()
        or np.any(np.diff(timestamps) <= 0.0)
        or np.any(np.diff(segments) < 0)
    ):
        raise GroundTrackPreparationError(
            "OEM samples are invalid for access prediction"
        )

    within_segment_gaps = np.diff(timestamps)[np.diff(segments) == 0]
    if (
        within_segment_gaps.size
        and float(np.max(within_segment_gaps)) > MAX_SOURCE_SAMPLE_GAP_S
    ):
        return StationAccess(
            station,
            (),
            "Access intervals unavailable: OEM sample spacing exceeds five minutes.",
        )

    intervals: list[AccessInterval] = []
    total_samples = 0
    segment_starts = np.r_[0, np.flatnonzero(np.diff(segments) != 0) + 1]
    segment_ends = np.r_[segment_starts[1:], timestamps.size]
    for start_index, end_index in zip(segment_starts, segment_ends):
        if end_index - start_index < 2:
            return StationAccess(
                station,
                (),
                "Access intervals unavailable: an OEM segment has fewer than two samples.",
            )
        segment_start = float(timestamps[start_index])
        segment_end = float(timestamps[end_index - 1])
        subdivisions = max(
            1,
            math.ceil((segment_end - segment_start) / MAX_ACCESS_SAMPLE_STEP_S),
        )
        segment_times = np.linspace(
            segment_start, segment_end, subdivisions + 1
        ).tolist()
        total_samples += len(segment_times)
        if total_samples > MAX_ACCESS_SAMPLES:
            return StationAccess(
                station,
                (),
                "Access intervals unavailable: OEM coverage requires too many samples.",
            )
        metrics = []
        for epoch in segment_times:
            resolved = cursor.lookup(epoch)
            metrics.append(
                None
                if resolved.state_m is None
                else _metrics_for_state(
                    station,
                    resolved.state_m,
                    source,
                    source.frame_name,
                    epoch,
                    position_cache,
                )
            )
        substep_access = [
            _refine_peak(
                station,
                cursor,
                source,
                source.frame_name,
                position_cache,
                segment_times[index - 1],
                segment_times[index + 1],
            )
            for index in range(1, len(segment_times) - 1)
            if metrics[index] is not None
            and not metrics[index].access
            and metrics[index - 1] is not None
            and metrics[index + 1] is not None
            and metrics[index].elevation_deg >= metrics[index - 1].elevation_deg
            and metrics[index].elevation_deg >= metrics[index + 1].elevation_deg
        ]
        for epoch, peak_metrics in substep_access:
            if peak_metrics.access:
                if any(
                    abs(epoch - existing_time) <= CROSSING_TIME_TOLERANCE_S
                    for existing_time in segment_times
                ):
                    continue
                insertion_index = int(np.searchsorted(segment_times, epoch))
                segment_times.insert(insertion_index, epoch)
                metrics.insert(insertion_index, peak_metrics)
        intervals.extend(
            _intervals_for_segment(
                station,
                cursor,
                source,
                source.frame_name,
                position_cache,
                segment_times,
                metrics,
                starts_at_coverage=start_index == 0,
                ends_at_coverage=end_index == timestamps.size,
                starts_after_gap=start_index > 0,
                ends_before_gap=end_index < timestamps.size,
            )
        )
    limitation = (
        "An access interval reaches an OEM segment gap; its crossing is unavailable."
        if any(
            interval.limited_by_gap_at_start or interval.limited_by_gap_at_end
            for interval in intervals
        )
        else None
    )
    return StationAccess(station, tuple(intervals), limitation)


def _refine_peak(
    station: GroundStation,
    cursor: OemCursor,
    source: GroundTrackSource,
    frame_name: str,
    position_cache: EarthFixedPositionCache,
    low_s: float,
    high_s: float,
) -> tuple[float, StationMetrics]:
    """Find a local elevation maximum inside one sampled bracket."""
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    first_s = high_s - ratio * (high_s - low_s)
    second_s = low_s + ratio * (high_s - low_s)

    def evaluate(epoch: float) -> StationMetrics:
        resolved = cursor.lookup(epoch)
        if resolved.state_m is None:
            raise GroundTrackPreparationError(
                f"OEM state unavailable while refining an access pass at {epoch:.3f}"
            )
        return _metrics_for_state(
            station, resolved.state_m, source, frame_name, epoch, position_cache
        )

    first_metrics = evaluate(first_s)
    second_metrics = evaluate(second_s)
    while high_s - low_s > CROSSING_TIME_TOLERANCE_S:
        if first_metrics.elevation_deg < second_metrics.elevation_deg:
            low_s = first_s
            first_s, first_metrics = second_s, second_metrics
            second_s = low_s + ratio * (high_s - low_s)
            second_metrics = evaluate(second_s)
        else:
            high_s = second_s
            second_s, second_metrics = first_s, first_metrics
            first_s = high_s - ratio * (high_s - low_s)
            first_metrics = evaluate(first_s)
    return (
        (first_s, first_metrics)
        if first_metrics.elevation_deg >= second_metrics.elevation_deg
        else (second_s, second_metrics)
    )


class StationAccessCache:
    """Share ECEF sample positions and pass histories across access views."""

    def __init__(self, position_cache: EarthFixedPositionCache | None = None) -> None:
        self.position_cache = (
            position_cache if position_cache is not None else EarthFixedPositionCache()
        )
        self._source: GroundTrackSource | None = None
        self._cursor: OemCursor | None = None
        self._results: dict[GroundStation, StationAccess] = {}

    def prepare(
        self,
        source: GroundTrackSource,
        cursor: OemCursor,
        station: GroundStation,
    ) -> StationAccess:
        if source is not self._source or cursor is not self._cursor:
            self._source = source
            self._cursor = cursor
            self._results.clear()
        result = self._results.get(station)
        if result is None:
            result = prepare_station_access(
                source, cursor, station, self.position_cache
            )
            self._results[station] = result
        return result

    def clear(self) -> None:
        """Invalidate all results after the cursor interpolation policy changes."""
        self._source = None
        self._cursor = None
        self._results.clear()

    def retain_stations(self, stations: Sequence[GroundStation]) -> None:
        """Discard cached results for removed or edited station definitions."""
        retained = set(stations)
        self._results = {
            station: result
            for station, result in self._results.items()
            if station in retained
        }


def _intervals_for_segment(
    station: GroundStation,
    cursor: OemCursor,
    source: GroundTrackSource,
    frame_name: str,
    position_cache: EarthFixedPositionCache,
    sample_times: Sequence[float],
    metrics: Sequence[StationMetrics | None],
    *,
    starts_at_coverage: bool,
    ends_at_coverage: bool,
    starts_after_gap: bool,
    ends_before_gap: bool,
) -> list[AccessInterval]:
    intervals: list[AccessInterval] = []
    active_start: float | None = None
    active_start_clipped = False
    current_values: list[tuple[float, StationMetrics]] = []
    previous_time: float | None = None
    previous_access = False
    for epoch, current_metrics in zip(sample_times, metrics):
        access = current_metrics is not None and current_metrics.access
        if access and not previous_access:
            if previous_time is None:
                active_start = epoch
                active_start_clipped = starts_at_coverage
            else:
                active_start = _refine_crossing(
                    station,
                    cursor,
                    source,
                    frame_name,
                    position_cache,
                    previous_time,
                    epoch,
                    entering=True,
                )
                active_start_clipped = False
            current_values = []
        if access and current_metrics is not None:
            if active_start is None:
                active_start = epoch
                active_start_clipped = starts_at_coverage
            current_values.append((epoch, current_metrics))
        if previous_access and not access and previous_time is not None:
            end_time = _refine_crossing(
                station,
                cursor,
                source,
                frame_name,
                position_cache,
                previous_time,
                epoch,
                entering=False,
            )
            if active_start is not None and current_values:
                intervals.append(
                    _make_interval(
                        active_start,
                        end_time,
                        current_values,
                        active_start_clipped,
                        False,
                        False,
                        False,
                    )
                )
            active_start = None
            current_values = []
        previous_time = epoch
        previous_access = access
    if active_start is not None and current_values:
        intervals.append(
            _make_interval(
                active_start,
                float(sample_times[-1]),
                current_values,
                active_start_clipped,
                ends_at_coverage,
                starts_after_gap and active_start == float(sample_times[0]),
                ends_before_gap,
            )
        )
    return intervals


def _refine_crossing(
    station: GroundStation,
    cursor: OemCursor,
    source: GroundTrackSource,
    frame_name: str,
    position_cache: EarthFixedPositionCache,
    low_s: float,
    high_s: float,
    *,
    entering: bool,
) -> float:
    while high_s - low_s > CROSSING_TIME_TOLERANCE_S:
        middle_s = (low_s + high_s) / 2.0
        state = cursor.lookup(middle_s)
        access = (
            state.state_m is not None
            and _metrics_for_state(
                station, state.state_m, source, frame_name, middle_s, position_cache
            ).access
        )
        if access == entering:
            high_s = middle_s
        else:
            low_s = middle_s
    return (low_s + high_s) / 2.0


def _metrics_for_state(
    station: GroundStation,
    state_m: np.ndarray,
    source: GroundTrackSource,
    frame_name: str,
    epoch_s: float,
    position_cache: EarthFixedPositionCache | None,
) -> StationMetrics:
    if position_cache is None:
        return station_metrics(station, state_m, frame_name, epoch_s)
    ecef_position_m = position_cache.position_for_state(source, state_m, epoch_s)
    return station_metrics_from_ecef(station, ecef_position_m)


def _make_interval(
    start_s: float,
    end_s: float,
    values: Sequence[tuple[float, StationMetrics]],
    clipped_at_start: bool,
    clipped_at_end: bool,
    limited_by_gap_at_start: bool,
    limited_by_gap_at_end: bool,
) -> AccessInterval:
    peak_time, peak_metrics = max(values, key=lambda item: item[1].elevation_deg)
    range_time, range_metrics = min(values, key=lambda item: item[1].slant_range_km)
    return AccessInterval(
        start_s,
        end_s,
        peak_metrics.elevation_deg,
        peak_time,
        range_metrics.slant_range_km,
        range_time,
        clipped_at_start,
        clipped_at_end,
        limited_by_gap_at_start,
        limited_by_gap_at_end,
    )
