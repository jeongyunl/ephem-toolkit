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
    station_metrics,
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
    frame_name: str,
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
            frame_name,
            epoch,
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
    frame_name: str,
    sample_times: Iterable[float],
    metrics: Iterable[StationMetrics | None],
    *,
    starts_at_coverage: bool,
    ends_at_coverage: bool,
    starts_after_gap: bool,
    ends_before_gap: bool,
) -> list[AccessInterval]:
    intervals: list[AccessInterval] = []
    active_interval: _ActiveAccessInterval | None = None
    first_time: float | None = None
    last_time: float | None = None
    previous_time: float | None = None
    previous_access = False
    for epoch, current_metrics in zip(sample_times, metrics):
        if first_time is None:
            first_time = epoch
        last_time = epoch
        if current_metrics is None:
            if (
                previous_access
                and previous_time is not None
                and active_interval is not None
            ):
                intervals.append(
                    active_interval.finish(
                        previous_time,
                        clipped_at_end=True,
                        limited_by_gap_at_start=False,
                        limited_by_gap_at_end=False,
                    )
                )
            active_interval = None
            previous_time = None
            previous_access = False
            continue
        access = current_metrics.access
        if access:
            if active_interval is None:
                if not previous_access and previous_time is not None:
                    active_start, active_start_metrics = _refine_crossing(
                        station,
                        cursor,
                        frame_name,
                        previous_time,
                        epoch,
                        entering=True,
                    )
                    active_start_clipped = False
                else:
                    active_start = epoch
                    active_start_metrics = current_metrics
                    active_start_clipped = starts_at_coverage
                active_interval = _ActiveAccessInterval(
                    active_start,
                    active_start_clipped,
                    active_start_metrics,
                    epoch,
                    current_metrics,
                    epoch,
                    current_metrics,
                    current_metrics,
                )
            else:
                active_interval.observe(epoch, current_metrics)
        if previous_access and not access and previous_time is not None:
            end_time, end_metrics = _refine_crossing(
                station,
                cursor,
                frame_name,
                previous_time,
                epoch,
                entering=False,
            )
            if active_interval is not None:
                intervals.append(
                    active_interval.finish(
                        end_time,
                        clipped_at_end=False,
                        limited_by_gap_at_start=False,
                        limited_by_gap_at_end=False,
                        end_metrics=end_metrics,
                    )
                )
            active_interval = None
        previous_time = epoch
        previous_access = access
    if active_interval is not None and last_time is not None:
        intervals.append(
            active_interval.finish(
                last_time,
                clipped_at_end=ends_at_coverage,
                limited_by_gap_at_start=(
                    starts_after_gap and active_interval.start_s == first_time
                ),
                limited_by_gap_at_end=ends_before_gap,
            )
        )
    return intervals


def _refine_crossing(
    station: GroundStation,
    cursor: StateCursor,
    frame_name: str,
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
                frame_name,
                middle_s,
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
        frame_name,
        crossing_s,
    )


def _metrics_for_state(
    station: GroundStation,
    state_m: np.ndarray,
    frame_name: str,
    epoch_s: float,
) -> StationMetrics:
    return station_metrics(station, state_m, frame_name, epoch_s)


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
