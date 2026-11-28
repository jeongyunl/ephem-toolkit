"""Ground-station access metrics and OEM-bounded pass preparation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np

from .cursor import CursorState
from .ground_stations import (
    GroundStation,
    StationMetrics,
    station_metrics_from_ecef,
)
from .ground_track import GroundTrackPreparationError

MAX_ACCESS_SAMPLE_STEP_S = 30.0
MAX_SOURCE_SAMPLE_GAP_S = 300.0
CROSSING_TIME_TOLERANCE_S = 0.5
MAX_ACCESS_SAMPLES = 1_000_000


class StateCursor(Protocol):
    """Cursor interface needed by access-boundary refinement."""

    def lookup(self, t: float, /) -> CursorState: ...


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
    start_azimuth_deg: float | None = None
    start_elevation_deg: float | None = None
    end_azimuth_deg: float | None = None
    end_elevation_deg: float | None = None


@dataclass
class _ActiveAccessInterval:
    start_s: float
    clipped_at_start: bool
    start_metrics: StationMetrics
    peak_time_s: float
    peak_metrics: StationMetrics
    minimum_range_time_s: float
    minimum_range_metrics: StationMetrics
    last_access_metrics: StationMetrics

    def observe(self, epoch: float, metrics: StationMetrics) -> None:
        if metrics.elevation_deg > self.peak_metrics.elevation_deg:
            self.peak_time_s = epoch
            self.peak_metrics = metrics
        if metrics.slant_range_km < self.minimum_range_metrics.slant_range_km:
            self.minimum_range_time_s = epoch
            self.minimum_range_metrics = metrics
        self.last_access_metrics = metrics

    def finish(
        self,
        end_s: float,
        *,
        clipped_at_end: bool,
        limited_by_gap_at_start: bool,
        limited_by_gap_at_end: bool,
        end_metrics: StationMetrics | None = None,
    ) -> AccessInterval:
        return _make_interval(
            self.start_s,
            end_s,
            self.peak_time_s,
            self.peak_metrics,
            self.minimum_range_time_s,
            self.minimum_range_metrics,
            self.clipped_at_start,
            clipped_at_end,
            limited_by_gap_at_start,
            limited_by_gap_at_end,
            self.start_metrics,
            self.last_access_metrics if end_metrics is None else end_metrics,
        )


@dataclass(frozen=True)
class ElevationProfile:
    """Sampled station elevation over one contiguous OEM segment."""

    times_s: np.ndarray
    elevations_deg: np.ndarray


@dataclass(frozen=True)
class LookAngleProfile:
    """Sampled look angles and slant range over one contiguous OEM segment."""

    times_s: np.ndarray
    azimuths_deg: np.ndarray
    elevations_deg: np.ndarray
    slant_ranges_km: np.ndarray | None = None


@dataclass(frozen=True)
class StationAccess:
    """Prepared access history and any prediction limitation for a station."""

    station: GroundStation
    intervals: tuple[AccessInterval, ...]
    limitation: str | None = None
    elevation_profiles: tuple[ElevationProfile, ...] = ()
    look_angle_profiles: tuple[LookAngleProfile, ...] = ()


def _refine_peak(
    station: GroundStation,
    cursor: StateCursor,
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
            station,
            resolved.state_m,
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


ACCESS_WINDOW_MARGIN_FRACTION = 0.5
ACCESS_WINDOW_MIN_MARGIN_S = 3_600.0


def _intervals_for_segment(
    station: GroundStation,
    cursor: StateCursor,
    sample_times: Iterable[float],
    metrics: Iterable[StationMetrics | None],
    *,
    starts_at_coverage: bool,
    ends_at_coverage: bool,
    starts_after_gap: bool,
    ends_before_gap: bool,
) -> list[AccessInterval]:
    times = np.asarray(tuple(sample_times), dtype=float)
    metric_values = tuple(metrics)
    if len(times) != len(metric_values):
        raise ValueError("station access sample times and metrics must have matching lengths")
    if len(times) == 0:
        return []
    valid = np.asarray(
        [metric is not None for metric in metric_values],
        dtype=bool,
    )
    access = np.asarray(
        [
            metric.access
            if metric is not None
            else False
            for metric in metric_values
        ],
        dtype=bool,
    )
    if not np.any(valid):
        return []

    intervals: list[AccessInterval] = []
    first_time = float(times[0])
    last_time = float(times[-1])

    run_starts = np.flatnonzero(
        valid
        & access
        & (
            (np.arange(len(times)) == 0)
            | ~valid[np.maximum(np.arange(len(times)) - 1, 0)]
            | ~access[np.maximum(np.arange(len(times)) - 1, 0)]
        )
    )
    run_stops: list[int] = []
    not_access_indices = np.flatnonzero(~(valid & access))
    for run_start in run_starts:
        position = int(np.searchsorted(not_access_indices, int(run_start), side="right"))
        stop = (
            int(not_access_indices[position])
            if position < len(not_access_indices)
            else len(times)
        )
        run_stops.append(stop)

    for run_start_value, run_stop in zip(run_starts, run_stops):
        run_start = int(run_start_value)
        if run_start >= run_stop:
            continue
        first_metric = metric_values[run_start]
        if first_metric is None:
            continue
        if run_start == 0:
            active_start = first_time
            active_start_metrics = first_metric
            active_start_clipped = starts_at_coverage
        elif valid[run_start - 1] and not access[run_start - 1]:
            active_start, active_start_metrics = _refine_crossing(
                station,
                cursor,
                float(times[run_start - 1]),
                float(times[run_start]),
                entering=True,
            )
            active_start_clipped = False
        elif not valid[run_start - 1]:
            active_start = float(times[run_start])
            active_start_metrics = first_metric
            active_start_clipped = starts_at_coverage
        else:
            active_start = float(times[run_start])
            active_start_metrics = first_metric
            active_start_clipped = False

        active_interval = _ActiveAccessInterval(
            active_start,
            active_start_clipped,
            active_start_metrics,
            float(times[run_start]),
            first_metric,
            float(times[run_start]),
            first_metric,
            first_metric,
        )
        run_metrics = [
            metric
            for metric in metric_values[run_start:run_stop]
            if metric is not None
        ]
        if run_metrics:
            run_times = times[run_start:run_stop]
            elevations = np.asarray(
                [metric.elevation_deg for metric in run_metrics],
                dtype=float,
            )
            ranges = np.asarray(
                [metric.slant_range_km for metric in run_metrics],
                dtype=float,
            )
            peak_offset = int(np.argmax(elevations))
            range_offset = int(np.argmin(ranges))
            peak_time = float(run_times[peak_offset])
            peak_metric = run_metrics[peak_offset]
            minimum_range_time = float(run_times[range_offset])
            minimum_range_metric = run_metrics[range_offset]
            if peak_metric.elevation_deg > active_interval.peak_metrics.elevation_deg:
                active_interval.peak_time_s = peak_time
                active_interval.peak_metrics = peak_metric
            elif peak_metric.elevation_deg == active_interval.peak_metrics.elevation_deg:
                if peak_time < active_interval.peak_time_s:
                    active_interval.peak_time_s = peak_time
                    active_interval.peak_metrics = peak_metric
            if minimum_range_metric.slant_range_km < active_interval.minimum_range_metrics.slant_range_km:
                active_interval.minimum_range_time_s = minimum_range_time
                active_interval.minimum_range_metrics = minimum_range_metric
            active_interval.last_access_metrics = run_metrics[-1]

        if run_stop < len(times):
            next_is_valid = valid[run_stop]
            next_is_access = access[run_stop]
            if next_is_valid and not next_is_access:
                end_time, end_metrics = _refine_crossing(
                    station,
                    cursor,
                    float(times[run_stop - 1]),
                    float(times[run_stop]),
                    entering=False,
                )
                intervals.append(
                    active_interval.finish(
                        end_time,
                        clipped_at_end=False,
                        limited_by_gap_at_start=False,
                        limited_by_gap_at_end=False,
                        end_metrics=end_metrics,
                    )
                )
            else:
                intervals.append(
                    active_interval.finish(
                        float(times[run_stop - 1]),
                        clipped_at_end=True,
                        limited_by_gap_at_start=False,
                        limited_by_gap_at_end=False,
                    )
                )
        else:
            intervals.append(
                active_interval.finish(
                    last_time,
                    clipped_at_end=ends_at_coverage,
                    limited_by_gap_at_start=(
                        starts_after_gap
                        and active_interval.start_s == first_time
                    ),
                    limited_by_gap_at_end=ends_before_gap,
                )
            )
    return intervals


def _refine_crossing(
    station: GroundStation,
    cursor: StateCursor,
    low_s: float,
    high_s: float,
    *,
    entering: bool,
) -> tuple[float, StationMetrics]:
    while high_s - low_s > CROSSING_TIME_TOLERANCE_S:
        middle_s = (low_s + high_s) / 2.0
        state = cursor.lookup(middle_s)
        access = (
            state.state_m is not None
            and _metrics_for_state(
                station,
                state.state_m,
            ).access
        )
        if access == entering:
            high_s = middle_s
        else:
            low_s = middle_s
    crossing_s = (low_s + high_s) / 2.0
    state = cursor.lookup(crossing_s)
    if state.state_m is None:
        raise GroundTrackPreparationError(
            f"OEM state unavailable at an access crossing at {crossing_s:.3f}"
        )
    return crossing_s, _metrics_for_state(
        station,
        state.state_m,
    )


def _metrics_for_state(
    station: GroundStation,
    state_m: np.ndarray,
) -> StationMetrics:
    """Calculate metrics for an Earth-fixed cursor state."""
    return station_metrics_from_ecef(station, state_m[:3])


def _make_interval(
    start_s: float,
    end_s: float,
    peak_time: float,
    peak_metrics: StationMetrics,
    range_time: float,
    range_metrics: StationMetrics,
    clipped_at_start: bool,
    clipped_at_end: bool,
    limited_by_gap_at_start: bool,
    limited_by_gap_at_end: bool,
    start_metrics: StationMetrics,
    end_metrics: StationMetrics,
) -> AccessInterval:
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
        start_metrics.azimuth_deg,
        start_metrics.elevation_deg,
        end_metrics.azimuth_deg,
        end_metrics.elevation_deg,
    )
