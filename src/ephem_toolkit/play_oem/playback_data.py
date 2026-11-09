"""Prepare inert backing state for the interactive player."""

from __future__ import annotations

from dataclasses import dataclass

from ephem_toolkit.core import time_utils
import numpy as np

from . import clock as playback_clock, cursor, series, time_unit
from .ground_track import GroundTrackSource


@dataclass
class PlaybackData:
    """File-dependent state installed in a playback window."""

    clock: playback_clock.PlaybackClock
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.OemCursor
    object_name: str
    frame_context: str
    dashboard_context: dict[str, str]
    metadata_details: tuple[tuple[str, str], ...]
    source_sample_count: int
    ground_track_source: GroundTrackSource | None = None
    oem_interpolation: str | None = None
    oem_interpolation_degree: int | None = None
    slider_bounds: tuple[float, float] | None = None


def oem_slider_bounds(
    start_time: str,
    stop_time: str,
    observed_bounds: tuple[float, float],
) -> tuple[float, float]:
    """Return an ordered slider domain using declared bounds plus observed data."""
    declared: list[float] = []
    for value in (start_time, stop_time):
        if not value.strip():
            continue
        try:
            declared.append(
                time_utils.datetime_to_tt_s(time_utils.iso8601_to_datetime(value))
            )
        except (TypeError, ValueError, OverflowError):
            continue
    candidates = [*observed_bounds, *declared]
    lower = min(candidates)
    upper = max(candidates)
    if len(declared) == 2 and declared[0] > declared[1]:
        return observed_bounds
    return lower, upper


def empty_playback_data() -> PlaybackData:
    """Create inert backing state for the window before an OEM is selected."""
    selected_time_unit = time_unit.TimeUnit.HOURS
    timestamp = 0.0
    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    orbit_series = series.compute_orbit_series([timestamp], [state], selected_time_unit)
    empty_clock = playback_clock.PlaybackClock(
        timestamp, timestamp, sample_times=[timestamp]
    )
    empty_cursor = cursor.OemCursor([timestamp], [state])
    return PlaybackData(
        empty_clock,
        orbit_series,
        selected_time_unit,
        empty_cursor,
        "No OEM loaded",
        "",
        {
            "object": "No OEM loaded",
            "frame": "",
            "center": "",
            "time_span": "",
            "sample_count": "0",
        },
        (
            ("Object ID", ""),
            ("Time system", ""),
            ("Frame epoch", ""),
            ("Usable start", ""),
            ("Usable stop", ""),
            ("Interpolation", ""),
            ("Interpolation degree", ""),
        ),
        0,
    )
