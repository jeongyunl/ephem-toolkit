"""Prepare inert backing state for the interactive player."""

from __future__ import annotations

from dataclasses import dataclass

from ephem_toolkit.core import time_utils
import numpy as np

from . import clock as playback_clock, cursor, series, time_unit


@dataclass
class PlaybackData:
    """File-dependent state installed in a playback window."""

    clock: playback_clock.PlaybackClock
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.StoreCursor
    object_name: str
    frame_context: str
    dashboard_context: dict[str, str]
    metadata_details: tuple[tuple[str, str], ...]
    source_sample_count: int
    oem_interpolation: str | None = None
    oem_interpolation_degree: int | None = None
    slider_bounds: tuple[float, float] | None = None


def oem_slider_bounds(
    start_time: str,
    stop_time: str,
    observed_bounds: tuple[float, float],
    *,
    time_system: str = "UTC",
) -> tuple[float, float]:
    """Return an ordered slider domain using declared bounds plus observed data."""
    declared = oem_declared_slider_bounds(
        start_time, stop_time, time_system=time_system
    )
    if declared is None:
        return observed_bounds
    return (
        min(observed_bounds[0], declared[0]),
        max(observed_bounds[1], declared[1]),
    )


def oem_declared_slider_bounds(
    start_time: str,
    stop_time: str,
    *,
    time_system: str = "UTC",
) -> tuple[float, float] | None:
    """Parse a valid UTC metadata interval into the slider's TT time domain."""
    if time_system.strip().upper() != "UTC":
        raise ValueError(
            "play-oem currently supports OEM TIME_SYSTEM = UTC only; "
            f"found {time_system.strip() or 'unspecified'!r}."
        )
    if not start_time.strip() or not stop_time.strip():
        return None
    try:
        start = time_utils.datetime_to_tt_s(
            time_utils.iso8601_to_datetime(start_time)
        )
        stop = time_utils.datetime_to_tt_s(time_utils.iso8601_to_datetime(stop_time))
    except (TypeError, ValueError, OverflowError):
        return None
    if start > stop:
        return None
    return start, stop


def empty_playback_data() -> PlaybackData:
    """Create inert backing state for the window before an OEM is selected."""
    selected_time_unit = time_unit.TimeUnit.HOURS
    timestamp = 0.0
    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    orbit_series = series.compute_orbit_series([timestamp], [state], selected_time_unit)
    empty_clock = playback_clock.PlaybackClock(
        timestamp, timestamp, sample_times=[timestamp]
    )
    empty_cursor = cursor.StoreCursor.empty()
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
