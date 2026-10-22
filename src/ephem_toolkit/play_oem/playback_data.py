"""Prepare an OEM and its playback data for the interactive player."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ephem_toolkit.core.time_utils as time_utils
import numpy as np

from . import clock as playback_clock, cursor, series, time_unit
from .data import read_oem_states


@dataclass
class PlaybackData:
    """All file-dependent state required by a playback window."""

    clock: playback_clock.PlaybackClock
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.OemCursor
    object_name: str
    frame_context: str
    dashboard_context: dict[str, str]
    metadata_details: tuple[tuple[str, str], ...]
    source_sample_count: int


def load_playback_data(source: str | Path) -> PlaybackData:
    """Read and prepare an entire OEM for playback."""
    oem_data, timestamps_s, states_m = read_oem_states(source)
    source_sample_count = len(states_m)
    # Choose the time-axis unit from the full span of this OEM.
    selected_time_unit = time_unit.TimeUnit.for_duration(
        timestamps_s[-1] - timestamps_s[0]
    )
    # Keep all samples and their segment IDs together across the full OEM span.
    segment_ids = oem_data.segment_ids[: len(timestamps_s)]
    orbit_series = series.compute_orbit_series(
        timestamps_s, states_m, selected_time_unit, segment_ids
    )
    # Clock defaults start paused at the first sample, at 1x speed without looping.
    clock = playback_clock.PlaybackClock(
        timestamps_s[0],
        timestamps_s[-1],
        sample_times=timestamps_s,
    )

    state_cursor = cursor.OemCursor(
        timestamps_s,
        states_m,
        interpolation=oem_data.meta.interpolation,
        interpolation_degree=oem_data.meta.interpolation_degree,
        segment_ids=segment_ids,
    )
    frame_context = (
        " / ".join(
            value
            for value in (
                oem_data.meta.ref_frame.strip(),
                oem_data.meta.center_name.strip(),
            )
            if value
        )
        or "Frame metadata unavailable"
    )
    object_name = oem_data.meta.object_name.strip() or Path(source).name
    dashboard_context = {
        "object": object_name,
        "frame": oem_data.meta.ref_frame.strip(),
        "center": oem_data.meta.center_name.strip(),
        "time_span": (
            f"{time_utils.datetime_to_iso8601(time_utils.tt_s_to_datetime(timestamps_s[0]))} – "
            f"{time_utils.datetime_to_iso8601(time_utils.tt_s_to_datetime(timestamps_s[-1]))}"
        ),
        "sample_count": str(len(timestamps_s)),
    }
    metadata_details = (
        ("Object ID", oem_data.meta.object_id),
        ("Time system", oem_data.meta.time_system),
        ("Frame epoch", oem_data.meta.ref_frame_epoch),
        ("Usable start", oem_data.meta.useable_start_time),
        ("Usable stop", oem_data.meta.useable_stop_time),
        ("Interpolation", oem_data.meta.interpolation or ""),
        (
            "Interpolation degree",
            (
                ""
                if oem_data.meta.interpolation_degree is None
                else str(oem_data.meta.interpolation_degree)
            ),
        ),
    )
    return PlaybackData(
        clock,
        orbit_series,
        selected_time_unit,
        state_cursor,
        object_name,
        frame_context,
        dashboard_context,
        metadata_details,
        source_sample_count,
    )


def empty_playback_data() -> PlaybackData:
    """Create inert backing state for the window before an OEM is selected."""
    # The existing controls expect non-empty clock and cursor objects. Keep one
    # private sample behind the empty UI; playback and graph controls stay disabled.
    # Use hours as a neutral placeholder until an OEM determines the axis unit.
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
