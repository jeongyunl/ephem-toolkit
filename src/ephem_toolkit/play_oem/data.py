"""OEM loading and duration filtering for playback."""

from __future__ import annotations

from pathlib import Path

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem


def read_oem_states(
    source: str | Path,
) -> tuple[oem.CcsdsOem, list[float], list[np.ndarray]]:
    """Read a CCSDS OEM and return time-ordered states.

    Parameters
    ----------
    source : str | Path
        Path to input OEM file.

    Returns
    -------
    tuple[oem.CcsdsOem, list[float], list[np.ndarray]]
        Parsed OEM object, timestamps in TT seconds since J2000, and 6D states in SI units
        [x, y, z, vx, vy, vz] with meters (m) and m/s.

    Raises
    ------
    FileNotFoundError
        If the input file path does not exist.
    ValueError
        If the OEM contains no state samples.
    """
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")

    oem_data: oem.CcsdsOem = oem.CcsdsOem.from_file(source_path)
    if not oem_data.states:
        raise ValueError(f"No state data found in OEM file: {source_path}")

    timestamps_s: list[float] = [timestamp_s for timestamp_s, _ in oem_data.states]
    states_m: list[np.ndarray] = [state_m for _, state_m in oem_data.states]
    return oem_data, timestamps_s, states_m


def filter_states_by_duration(
    timestamps_s: list[float],
    states_m: list[np.ndarray],
    duration_s: float | None,
) -> tuple[list[float], list[np.ndarray]]:
    """Filter state history to [start, start + duration].

    Parameters
    ----------
    timestamps_s : list[float]
        State timestamps in TT seconds since J2000.
    states_m : list[np.ndarray]
        State vectors in SI units [x, y, z, vx, vy, vz].
    duration_s : float | None
        Duration from first timestamp in seconds, or None for full span.

    Returns
    -------
    tuple[list[float], list[np.ndarray]]
        Filtered timestamps and states.

    Raises
    ------
    ValueError
        If duration filtering removes all samples.
    """
    if duration_s is None:
        return timestamps_s, states_m

    start_time_s: float = timestamps_s[0]
    stop_time_s: float = start_time_s + duration_s

    filtered_timestamps_s: list[float] = []
    filtered_states_m: list[np.ndarray] = []

    for timestamp_s, state_m in zip(timestamps_s, states_m):
        if timestamp_s <= stop_time_s:
            filtered_timestamps_s.append(timestamp_s)
            filtered_states_m.append(state_m)

    if not filtered_timestamps_s:
        raise ValueError("No states remain after duration filtering.")

    return filtered_timestamps_s, filtered_states_m
