"""Plot and compare multiple orbit trajectories."""

from __future__ import annotations

from .plot_orbit_deltas import main
from .constants import INTERPOLATION_DEGREE, METERS_TO_KILOMETERS
from .csv_utils import generate_csv_path, sanitize_filename_component, write_csv
from .data_structures import StateHistory, TimeUnit
from .file_io import read_orbit_file
from .plotting import (
    convert_state_to_km,
    plot_angular_separation,
    plot_orbits,
    plot_relative_cartesian_timeseries,
    plot_relative_rtn_orbits,
    plot_relative_rtn_timeseries,
)

__all__ = [
    # Constants
    "INTERPOLATION_DEGREE",
    "METERS_TO_KILOMETERS",
    # Data structures
    "StateHistory",
    "TimeUnit",
    # File I/O
    "read_orbit_file",
    # CSV utilities
    "sanitize_filename_component",
    "write_csv",
    "generate_csv_path",
    # Plotting
    "convert_state_to_km",
    "plot_orbits",
    "plot_relative_cartesian_timeseries",
    "plot_relative_rtn_timeseries",
    "plot_angular_separation",
    "plot_relative_rtn_orbits",
    # CLI
    "main",
]
