"""File I/O functions for orbit delta plotting."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ephem_toolkit.core.ccsds import oem
from ephem_toolkit.core.ccsds.oem import CcsdsOem


def read_orbit_file(source: str | Path) -> dict[float, np.ndarray]:
    """Read an OEM or raw-state file and return state history.

    Parameters
    ----------
    source : str | Path
        Path to the OEM or raw-state file.

    Returns
    -------
    dict[float, np.ndarray]
        State history: dictionary mapping epoch timestamps (float, seconds since epoch) to
        state vectors (6-element numpy arrays [x, y, z, vx, vy, vz] in m and m/s).

    Notes
    -----
    The OEM reader returns state vectors in SI units (m, m/s). These will be converted
    to km and km/s for plotting and CSV export by the plotting functions.
    """
    source_path: Path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")

    state_history: dict[float, np.ndarray] = {}

    # Try reading as OEM file first (more robust)
    try:
        oem_data = CcsdsOem.read(source_path)
        # Convert to dict for compatibility with existing plotting code
        state_history = {timestamp: state for timestamp, state in oem_data.states}
        return state_history
    except Exception:
        pass

    # Fall back to line-by-line parsing for raw state files
    with open(source_path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            try:
                result: tuple[float, np.ndarray] | None = oem.parse_oem_state_line(line)
                if result is not None:
                    timestamp, state = result
                    state_history[timestamp] = state
            except ValueError:
                # Skip lines that don't parse (headers, comments, etc.)
                continue

    if not state_history:
        raise ValueError(f"Could not parse any state data from {source_path}")

    return state_history
