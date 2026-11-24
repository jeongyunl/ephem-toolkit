"""Shared snapping helpers for playback timestamps."""

from __future__ import annotations

import math

from ephem_toolkit.core import time_utils


UTC_HALF_SECOND_S = 0.5


def snap_tt_s_to_utc_half_second(tt_s: float) -> float:
    """Snap TT seconds to the nearest half-second boundary in UTC.

    The epoch is shifted by the modeled TT−UTC offset, quantized on the UTC
    grid, then shifted back to TT. Halfway cases round toward the later instant.
    """
    if (
        isinstance(tt_s, bool)
        or not isinstance(tt_s, (int, float))
        or not math.isfinite(tt_s)
    ):
        raise ValueError("tt_s must be a finite number")
    tt = float(tt_s)
    tt_minus_utc = time_utils.tt_minus_utc_seconds(tt)
    utc_s_from_j2000 = tt - tt_minus_utc
    # J2000 is noon UTC. Shift to a midnight-based axis before quantizing so
    # this remains a civil UTC grid rather than a grid relative to TT seconds.
    utc_s_from_midnight = utc_s_from_j2000 + 43_200.0
    grid_index = math.floor(utc_s_from_midnight / UTC_HALF_SECOND_S + 0.5)
    snapped_utc_s_from_j2000 = grid_index * UTC_HALF_SECOND_S - 43_200.0
    return snapped_utc_s_from_j2000 + tt_minus_utc
