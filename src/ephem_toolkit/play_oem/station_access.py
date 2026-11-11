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
    active_start: float | None = None
    active_start_clipped = False
    active_start_metrics: StationMetrics | None = None
    peak_time: float | None = None
    peak_metrics: StationMetrics | None = None
    range_time: float | None = None
    range_metrics: StationMetrics | None = None
    last_access_metrics: StationMetrics | None = None
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
                and active_start is not None
                and active_start_metrics is not None
                and peak_time is not None
                and peak_metrics is not None
                and range_time is not None
                and range_metrics is not None
                and last_access_metrics is not None
            ):
                intervals.append(
                    _make_interval(
                        active_start,
                        previous_time,
                        peak_time,
                        peak_metrics,
                        range_time,
                        range_metrics,
                        active_start_clipped,
                        True,
                        False,
                        False,
                        active_start_metrics,
                        last_access_metrics,
                    )
                )
            active_start = None
            active_start_metrics = None
            peak_time = None
            peak_metrics = None
            range_time = None
            range_metrics = None
            last_access_metrics = None
            previous_time = None
            previous_access = False
            continue
        access = current_metrics is not None and current_metrics.access
        if access and not previous_access:
            if previous_time is None:
                active_start = epoch
                active_start_clipped = starts_at_coverage
                active_start_metrics = current_metrics
            else:
                active_start, active_start_metrics = _refine_crossing(
                    station,
                    cursor,
                    frame_name,
                    previous_time,
                    epoch,
                    entering=True,
                )
                active_start_clipped = False
        if access and current_metrics is not None:
            if active_start is None:
                active_start = epoch
                active_start_clipped = starts_at_coverage
                active_start_metrics = current_metrics
            if peak_metrics is None or (
                current_metrics.elevation_deg > peak_metrics.elevation_deg
            ):
                peak_time, peak_metrics = epoch, current_metrics
            if range_metrics is None or (
                current_metrics.slant_range_km < range_metrics.slant_range_km
            ):
                range_time, range_metrics = epoch, current_metrics
            last_access_metrics = current_metrics
        if previous_access and not access and previous_time is not None:
            end_time, end_metrics = _refine_crossing(
                station,
                cursor,
                frame_name,
                previous_time,
                epoch,
                entering=False,
            )
            if (
                active_start is not None
                and peak_metrics is not None
                and peak_time is not None
                and range_metrics is not None
                and range_time is not None
                and active_start_metrics is not None
            ):
                intervals.append(
                    _make_interval(
                        active_start,
                        end_time,
                        peak_time,
                        peak_metrics,
                        range_time,
                        range_metrics,
                        active_start_clipped,
                        False,
                        False,
                        False,
                        active_start_metrics,
                        end_metrics,
                    )
                )
            active_start = None
            active_start_metrics = None
            peak_time = None
            peak_metrics = None
            range_time = None
            range_metrics = None
            last_access_metrics = None
        previous_time = epoch
        previous_access = access
    if (
        active_start is not None
        and last_time is not None
        and peak_time is not None
        and peak_metrics is not None
        and range_time is not None
        and range_metrics is not None
        and last_access_metrics is not None
        and active_start_metrics is not None
    ):
        intervals.append(
            _make_interval(
                active_start,
                last_time,
                peak_time,
                peak_metrics,
                range_time,
                range_metrics,
                active_start_clipped,
                ends_at_coverage,
                starts_after_gap and active_start == first_time,
                ends_before_gap,
                active_start_metrics,
                last_access_metrics,
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
