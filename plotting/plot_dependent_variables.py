#!/usr/bin/env python3
"""Plot dependent-variable results from a saved Tudat CSV file.

This script reads the ``*_dep_vars.csv`` format produced by
``propagate_orbit.py`` and recreates the dependent-variable plots.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.time_utils as time_utils

SECONDS_PER_HOUR: float = 3600.0
"""Conversion factor from seconds to hours."""

HOURS_PER_DAY: float = 24.0
"""Number of hours in one day."""

KILOMETERS_TO_METERS: float = 1e3
"""Conversion factor from kilometers to meters."""

PLOT_STANDARD_FIGURE_SIZE_IN: tuple[int, int] = (9, 5)
"""Default figure size (width, height) in inches for standard plots."""

PLOT_KEPLER_FIGURE_SIZE_IN: tuple[int, int] = (9, 12)
"""Figure size (width, height) in inches for Keplerian element plots."""

PLOT_GROUND_TRACK_H: int = 3
"""Duration in hours to display for ground track plots."""

PLOT_SCATTER_MARKER_SIZE_PT2: int = 1
"""Marker size in points² for scatter plots."""

PLOT_LATITUDE_TICK_STEP_DEG: int = 45
"""Tick spacing in degrees for latitude axes."""

PLOT_TRUE_ANOMALY_TICK_STEP_DEG: int = 60
"""Tick spacing in degrees for true anomaly axes."""

EARTH_MEAN_RADIUS_KM: float = 6378.137
"""Earth mean radius in kilometers (WGS-84)."""


# ===================================================================
# Data structures
# ===================================================================


@dataclass(frozen=True)
class DepVarColumnMeta:
    """Parsed metadata for one dependent-variable CSV column."""

    header: str
    """Original CSV column header string"""
    dep_type: str
    """Dependent-variable type identifier (e.g., 'keplerian_state', 'total_acceleration')"""
    acceleration_model_type: str
    """Acceleration model type (e.g., 'point_mass_gravity', 'aerodynamic'); empty for non-acceleration types"""
    associated_body: str
    """Primary body associated with this variable (e.g., satellite name)"""
    secondary_body: str
    """Secondary body (e.g., 'Earth'); empty when not applicable"""
    component_index: str
    """Raw component index string from the header; empty for scalar quantities"""
    vector_component_index: int | None
    """Integer component index for vector quantities (0, 1, 2, …); None for scalars"""
    column_key: str
    """Unique dictionary key used to look up this column in dep_var_columns; may include a '#dup' suffix for duplicates"""
    occurrence_index: int
    """Zero-based count of how many times this header appeared before this column"""


@dataclass
class CsvDependentVariableData:
    """CSV-backed dependent-variable data and parsed metadata."""

    time_history_tdb_s: np.ndarray
    """Epoch timestamps in TDB seconds, shape (N,)"""
    dep_var_columns: dict[str, np.ndarray]
    """Mapping of column_key to 1-D data array, each of shape (N,)"""
    metadata: list[DepVarColumnMeta]
    """Per-column metadata in the same order as the CSV columns"""


# ===================================================================
# CSV I/O functions
# ===================================================================


def read_dependent_variables_csv(
    dep_var_csv_path: str | Path,
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Read dependent-variable CSV data into numeric arrays.

    Parameters
    ----------
    dep_var_csv_path : str | Path
        Path to the dependent-variable CSV file.

    Returns
    -------
    tuple[np.ndarray, list[str], np.ndarray]
        A tuple of (time_history_tdb_s, dep_var_headers, dep_var_matrix).
    """
    with open(dep_var_csv_path, "r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise ValueError("dependent-variable CSV is empty") from exc

        if not headers:
            raise ValueError("dependent-variable CSV header is missing")
        if headers[0] != "epoch_tdb_s":
            raise ValueError(
                "invalid dependent-variable CSV header: first column must be 'epoch_tdb_s'"
            )

        numeric_rows = []
        expected_column_count = len(headers)
        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != expected_column_count:
                raise ValueError(
                    "invalid dependent-variable CSV row width at line "
                    f"{row_number}: expected {expected_column_count} columns, got {len(row)}"
                )
            try:
                numeric_rows.append([float(value) for value in row])
            except ValueError as exc:
                raise ValueError(
                    "invalid dependent-variable CSV numeric value at line "
                    f"{row_number}"
                ) from exc

    if not numeric_rows:
        return np.array([], dtype=float), headers[1:], np.empty((0, len(headers) - 1))

    data = np.asarray(numeric_rows, dtype=float)
    time_history_tdb_s = data[:, 0]
    dep_var_headers = headers[1:]
    dep_var_matrix = data[:, 1:]

    return time_history_tdb_s, dep_var_headers, dep_var_matrix


def parse_dep_var_column_metadata(
    header: str,
    column_key: str,
    occurrence_index: int,
) -> DepVarColumnMeta:
    """Parse one dependent-variable header into structured metadata.

    Parameters
    ----------
    header : str
        The CSV column header string.
    column_key : str
        The unique dictionary key for this column.
    occurrence_index : int
        Zero-based count of how many times this header appeared before.

    Returns
    -------
    DepVarColumnMeta
        Parsed metadata for the column.
    """
    parts: list[str] = header.split("/")
    dep_type: str = parts[0] if len(parts) > 0 else ""
    acceleration_model_type: str = parts[1] if len(parts) > 1 else ""
    associated_body: str = parts[2] if len(parts) > 2 else ""
    secondary_body: str = parts[3] if len(parts) > 3 else ""
    component_index: str = parts[4] if len(parts) > 4 else ""

    vector_component_index: int | None = None
    if parts and parts[-1].isdigit():
        vector_component_index = int(parts[-1])

    return DepVarColumnMeta(
        header=header,
        dep_type=dep_type,
        acceleration_model_type=acceleration_model_type,
        associated_body=associated_body,
        secondary_body=secondary_body,
        component_index=component_index,
        vector_component_index=vector_component_index,
        column_key=column_key,
        occurrence_index=occurrence_index,
    )


def load_csv_dependent_variable_data(
    dep_var_csv_path: str | Path,
) -> CsvDependentVariableData:
    """Load CSV dependent-variable data and parse per-column metadata.

    Parameters
    ----------
    dep_var_csv_path : str | Path
        Path to the dependent-variable CSV file.

    Returns
    -------
    CsvDependentVariableData
        Loaded data with parsed metadata.
    """
    time_history_tdb_s, dep_var_headers, dep_var_matrix = read_dependent_variables_csv(
        dep_var_csv_path
    )

    occurrence_counter: dict[str, int] = {}
    dep_var_columns: dict[str, np.ndarray] = {}
    metadata: list[DepVarColumnMeta] = []
    for column_index, header in enumerate(dep_var_headers):
        occurrence_index = occurrence_counter.get(header, 0)
        occurrence_counter[header] = occurrence_index + 1
        column_key = (
            header if occurrence_index == 0 else f"{header}#dup{occurrence_index}"
        )
        dep_var_columns[column_key] = dep_var_matrix[:, column_index]
        metadata.append(
            parse_dep_var_column_metadata(
                header=header,
                column_key=column_key,
                occurrence_index=occurrence_index,
            )
        )

    return CsvDependentVariableData(
        time_history_tdb_s=time_history_tdb_s,
        dep_var_columns=dep_var_columns,
        metadata=metadata,
    )


# ===================================================================
# Data extraction helpers
# ===================================================================


def _filter_metadata(
    data: CsvDependentVariableData,
    dep_type: str,
    acceleration_model_type: str | None = None,
    associated_body: str | None = None,
    secondary_body: str | None = None,
) -> list[DepVarColumnMeta]:
    """Filter metadata by dependent-variable type and optional constraints.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    dep_type : str
        Dependent-variable type to match.
    acceleration_model_type : str | None, optional
        Acceleration model type filter (default: None).
    associated_body : str | None, optional
        Associated body filter (default: None).
    secondary_body : str | None, optional
        Secondary body filter (default: None).

    Returns
    -------
    list[DepVarColumnMeta]
        Matching metadata entries.
    """
    matching = []
    for meta in data.metadata:
        if meta.dep_type != dep_type:
            continue
        if (
            acceleration_model_type is not None
            and meta.acceleration_model_type != acceleration_model_type
        ):
            continue
        if associated_body is not None and meta.associated_body != associated_body:
            continue
        if secondary_body is not None and meta.secondary_body != secondary_body:
            continue
        matching.append(meta)
    return matching


def _extract_scalar(
    data: CsvDependentVariableData,
    dep_type: str,
    acceleration_model_type: str | None = None,
    associated_body: str | None = None,
    secondary_body: str | None = None,
    occurrence_index: int = 0,
) -> np.ndarray:
    """Extract a scalar dependent-variable column.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    dep_type : str
        Dependent-variable type to extract.
    acceleration_model_type : str | None, optional
        Acceleration model type filter (default: None).
    associated_body : str | None, optional
        Associated body filter (default: None).
    secondary_body : str | None, optional
        Secondary body filter (default: None).
    occurrence_index : int, optional
        Which occurrence to extract if multiple matches (default: 0).

    Returns
    -------
    np.ndarray
        The scalar data array.

    Raises
    ------
    KeyError
        If no matching column is found.
    """
    matches = [
        meta
        for meta in _filter_metadata(
            data,
            dep_type=dep_type,
            acceleration_model_type=acceleration_model_type,
            associated_body=associated_body,
            secondary_body=secondary_body,
        )
        if meta.vector_component_index is None
    ]
    if not matches:
        raise KeyError(
            "missing scalar dependent-variable column for "
            f"dep_type={dep_type}, acceleration_model_type={acceleration_model_type}, "
            f"associated_body={associated_body}, secondary_body={secondary_body}"
        )
    if occurrence_index >= len(matches):
        raise KeyError(
            "missing scalar dependent-variable column occurrence for "
            f"dep_type={dep_type}, occurrence_index={occurrence_index}"
        )
    return data.dep_var_columns[matches[occurrence_index].column_key]


def _extract_vector(
    data: CsvDependentVariableData,
    dep_type: str,
    associated_body: str | None = None,
    secondary_body: str | None = None,
) -> np.ndarray:
    """Extract a vector dependent-variable (3 components).

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    dep_type : str
        Dependent-variable type to extract.
    associated_body : str | None, optional
        Associated body filter (default: None).
    secondary_body : str | None, optional
        Secondary body filter (default: None).

    Returns
    -------
    np.ndarray
        The vector data array with shape (N, 3).

    Raises
    ------
    KeyError
        If no matching columns are found.
    """
    matches = [
        meta
        for meta in _filter_metadata(
            data,
            dep_type=dep_type,
            associated_body=associated_body,
            secondary_body=secondary_body,
        )
        if meta.vector_component_index is not None
    ]
    if not matches:
        raise KeyError(
            "missing vector dependent-variable columns for "
            f"dep_type={dep_type}, associated_body={associated_body}, secondary_body={secondary_body}"
        )

    matches.sort(key=lambda item: item.vector_component_index)
    return np.column_stack([data.dep_var_columns[meta.column_key] for meta in matches])


def _extract_latitude_longitude(
    data: CsvDependentVariableData,
    satellite_name: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract latitude/longitude with compatibility for Tudat header variants.

    Tudat may export latitude under different dep_type names depending on the
    dependent-variable setting used (e.g. ``latitude``, ``geodetic_latitude``)
    and longitude as either ``longitude`` or
    ``relative_body_aerodynamic_orientation_angle``.  This function tries
    multiple known combinations to locate the correct columns.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    satellite_name : str
        Name of the satellite for filtering.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Latitude and longitude arrays in radians.

    Raises
    ------
    KeyError
        If no matching latitude/longitude columns are found.
    """
    # Known dep_type names that represent latitude
    latitude_dep_types = ["latitude", "geodetic_latitude"]
    # Known dep_type names that represent longitude
    longitude_dep_types = ["longitude", "relative_body_aerodynamic_orientation_angle"]

    fallback_constraints = [
        (satellite_name, "Earth"),
        (satellite_name, None),
        (None, "Earth"),
        (None, None),
    ]

    # Strategy 1: find separate latitude and longitude columns by their dep_type names
    for associated_body, secondary_body in fallback_constraints:
        latitude_rad = None
        longitude_rad = None

        # Try to find latitude
        for lat_type in latitude_dep_types:
            try:
                latitude_rad = _extract_scalar(
                    data,
                    dep_type=lat_type,
                    associated_body=associated_body,
                    secondary_body=secondary_body,
                )
                break
            except KeyError:
                continue

        if latitude_rad is None:
            continue

        # Try to find longitude
        for lon_type in longitude_dep_types:
            try:
                longitude_rad = _extract_scalar(
                    data,
                    dep_type=lon_type,
                    associated_body=associated_body,
                    secondary_body=secondary_body,
                )
                break
            except KeyError:
                continue

        if longitude_rad is not None:
            return latitude_rad, longitude_rad

    # Strategy 2: two relative_body_aerodynamic_orientation_angle columns
    # (legacy format where both lat and lon share the same dep_type)
    for associated_body, secondary_body in fallback_constraints:
        try:
            latitude_rad = _extract_scalar(
                data,
                dep_type="relative_body_aerodynamic_orientation_angle",
                associated_body=associated_body,
                secondary_body=secondary_body,
                occurrence_index=0,
            )
            longitude_rad = _extract_scalar(
                data,
                dep_type="relative_body_aerodynamic_orientation_angle",
                associated_body=associated_body,
                secondary_body=secondary_body,
                occurrence_index=1,
            )
            return latitude_rad, longitude_rad
        except KeyError:
            continue

    raise KeyError(
        "missing latitude/longitude columns in dependent-variable CSV. "
        "Expected either latitude/longitude columns (dep_type: "
        "latitude|geodetic_latitude and longitude|relative_body_aerodynamic_orientation_angle) "
        "or two relative_body_aerodynamic_orientation_angle columns."
    )


def _extract_central_body_fixed_position(
    data: CsvDependentVariableData,
    satellite_name: str,
) -> np.ndarray:
    """Extract Earth-fixed cartesian position with compatibility for header variants.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    satellite_name : str
        Name of the satellite for filtering.

    Returns
    -------
    np.ndarray
        Earth-fixed position array with shape (N, 3).

    Raises
    ------
    KeyError
        If no matching position columns are found.
    """
    candidate_dep_types = [
        "central_body_fixed_cartesian_position",
        "body_fixed_relative_cartesian_position",
    ]
    fallback_constraints = [
        (satellite_name, "Earth"),
        (satellite_name, None),
        (None, "Earth"),
        (None, None),
    ]

    for dep_type in candidate_dep_types:
        for associated_body, secondary_body in fallback_constraints:
            try:
                return _extract_vector(
                    data,
                    dep_type=dep_type,
                    associated_body=associated_body,
                    secondary_body=secondary_body,
                )
            except KeyError:
                continue

    raise KeyError(
        "missing Earth-fixed cartesian position columns in dependent-variable CSV. "
        "Expected central_body_fixed_cartesian_position or "
        "body_fixed_relative_cartesian_position columns."
    )


def _extract_relative_position(
    data: CsvDependentVariableData,
    satellite_name: str,
) -> np.ndarray:
    """Extract relative cartesian position with compatibility for header variants.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    satellite_name : str
        Name of the satellite for filtering.

    Returns
    -------
    np.ndarray
        Relative position array with shape (N, 3).

    Raises
    ------
    KeyError
        If no matching position columns are found.
    """
    candidate_dep_types = ["relative_position"]
    fallback_constraints = [
        (satellite_name, "Earth"),
        (satellite_name, None),
        (None, "Earth"),
        (None, None),
    ]

    for dep_type in candidate_dep_types:
        for associated_body, secondary_body in fallback_constraints:
            try:
                return _extract_vector(
                    data,
                    dep_type=dep_type,
                    associated_body=associated_body,
                    secondary_body=secondary_body,
                )
            except KeyError:
                continue

    raise KeyError(
        "missing relative cartesian position columns in dependent-variable CSV. "
        "Expected relative_position columns."
    )


# ===================================================================
# Plotting functions
# ===================================================================


def plot_total_acceleration(
    data: CsvDependentVariableData, relative_time_h: np.ndarray, satellite_name: str
) -> None:
    """Plot total acceleration norm over time.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    relative_time_h : np.ndarray
        Time array in hours relative to start.
    satellite_name : str
        Name of the satellite for labels.
    """
    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    plt.title(
        f"Total acceleration norm on {satellite_name} over the course of propagation."
    )
    satellite_total_acceleration_mps2 = _extract_vector(
        data,
        dep_type="total_acceleration",
        associated_body=satellite_name,
    )
    total_acceleration_norm_mps2 = np.linalg.norm(
        satellite_total_acceleration_mps2, axis=1
    )
    plt.plot(relative_time_h, total_acceleration_norm_mps2)
    plt.xlabel("Time [hr]")
    plt.ylabel("Total Acceleration [m/s$^2$]")
    plt.grid()
    plt.tight_layout()


def plot_ground_track(
    data: CsvDependentVariableData, relative_time_h: np.ndarray, satellite_name: str
) -> None:
    """Plot ground track (latitude/longitude) for first 3 hours.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    relative_time_h : np.ndarray
        Time array in hours relative to start.
    satellite_name : str
        Name of the satellite for labels.
    """
    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    plt.title(f"3 hour ground track of {satellite_name}")
    latitude_rad, longitude_rad = _extract_latitude_longitude(data, satellite_name)
    subset_count = int(len(relative_time_h) / HOURS_PER_DAY * PLOT_GROUND_TRACK_H)
    latitude_deg = np.rad2deg(latitude_rad[0:subset_count])
    longitude_deg = np.rad2deg(longitude_rad[0:subset_count])
    plt.scatter(longitude_deg, latitude_deg, s=PLOT_SCATTER_MARKER_SIZE_PT2)
    plt.xlabel("Longitude [deg]")
    plt.ylabel("Latitude [deg]")
    plt.yticks(np.arange(-90, 91, step=PLOT_LATITUDE_TICK_STEP_DEG))
    plt.grid()
    plt.tight_layout()


def plot_kepler_elements(
    data: CsvDependentVariableData, relative_time_h: np.ndarray, satellite_name: str
) -> None:
    """Plot evolution of Keplerian orbital elements.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    relative_time_h : np.ndarray
        Time array in hours relative to start.
    satellite_name : str
        Name of the satellite for labels.
    """
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(
        3, 2, figsize=PLOT_KEPLER_FIGURE_SIZE_IN
    )
    fig.suptitle("Evolution of Kepler elements over the course of the propagation.")

    kepler_elements = _extract_vector(
        data,
        dep_type="keplerian_state",
        associated_body=satellite_name,
        secondary_body="Earth",
    )

    semi_major_axis_km = kepler_elements[:, 0] / KILOMETERS_TO_METERS
    ax1.plot(relative_time_h, semi_major_axis_km)
    ax1.set_ylabel("Semi-major axis [km]")

    eccentricity = kepler_elements[:, 1]
    ax2.plot(relative_time_h, eccentricity)
    ax2.set_ylabel("Eccentricity [-]")

    inclination_deg = np.rad2deg(kepler_elements[:, 2])
    ax3.plot(relative_time_h, inclination_deg)
    ax3.set_ylabel("Inclination [deg]")

    argument_of_periapsis_deg = np.rad2deg(kepler_elements[:, 3])
    ax4.plot(relative_time_h, argument_of_periapsis_deg)
    ax4.set_ylabel("Argument of Periapsis [deg]")

    raan_deg = np.rad2deg(kepler_elements[:, 4])
    ax5.plot(relative_time_h, raan_deg)
    ax5.set_ylabel("RAAN [deg]")

    true_anomaly_deg = np.rad2deg(kepler_elements[:, 5])
    ax6.scatter(relative_time_h, true_anomaly_deg, s=PLOT_SCATTER_MARKER_SIZE_PT2)
    ax6.set_ylabel("True Anomaly [deg]")
    ax6.set_yticks(np.arange(0, 361, step=PLOT_TRUE_ANOMALY_TICK_STEP_DEG))

    for ax in fig.get_axes():
        ax.set_xlabel("Time [hr]")
        ax.grid()
    plt.tight_layout()


def plot_acceleration_components(
    data: CsvDependentVariableData, relative_time_h: np.ndarray, satellite_name: str
) -> None:
    """Plot acceleration components by type and origin.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    relative_time_h : np.ndarray
        Time array in hours relative to start.
    satellite_name : str
        Name of the satellite for labels.
    """
    acceleration_type_to_string = {
        "point_mass_gravity": "Point Mass",
        "spherical_harmonic_gravity": "SphHarm Grav",
        "aerodynamic": "Aerodynamic Drag",
        "radiation_pressure": "Radiation Pressure",
    }

    plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)

    single_acc_norm_columns = [
        meta
        for meta in data.metadata
        if meta.dep_type == "single_acceleration_norm"
        and meta.vector_component_index is None
    ]

    for meta in single_acc_norm_columns:
        acceleration_norm_mps2 = data.dep_var_columns[meta.header]
        accel_label = acceleration_type_to_string.get(
            meta.acceleration_model_type,
            meta.acceleration_model_type or "unknown",
        )
        label = f"{accel_label}: {meta.secondary_body}"
        plt.plot(relative_time_h, acceleration_norm_mps2, label=label)

    plt.xlabel("Time [hr]")
    plt.ylabel("Acceleration Norm [m/s$^2$]")
    plt.legend(bbox_to_anchor=(1.005, 1))
    plt.suptitle(
        f"Accelerations norms on {satellite_name}, distinguished by type and origin, over the course of propagation."
    )
    plt.yscale("log")
    plt.grid()
    plt.tight_layout()


def plot_satellite_body_fixed_position_history_3d(
    data: CsvDependentVariableData, satellite_name: str
) -> FuncAnimation | None:
    """Create 3D animated plot of satellite position in Earth-fixed frame.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    satellite_name : str
        Name of the satellite for labels.

    Returns
    -------
    FuncAnimation | None
        Animation object, or None if no position data available.
    """
    positions_m = _extract_central_body_fixed_position(data, satellite_name)
    if positions_m.size == 0:
        return None
    positions_km = positions_m / KILOMETERS_TO_METERS

    fig = plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    ax = fig.add_subplot(111, projection="3d")

    azimuth = np.linspace(0.0, 2.0 * np.pi, 60)
    polar = np.linspace(0.0, np.pi, 30)
    earth_x = EARTH_MEAN_RADIUS_KM * np.outer(np.cos(azimuth), np.sin(polar))
    earth_y = EARTH_MEAN_RADIUS_KM * np.outer(np.sin(azimuth), np.sin(polar))
    earth_z = EARTH_MEAN_RADIUS_KM * np.outer(np.ones_like(azimuth), np.cos(polar))
    ax.plot_surface(earth_x, earth_y, earth_z, color="lightskyblue", alpha=0.35)

    polar_axis_extent_km = 1.5 * EARTH_MEAN_RADIUS_KM
    ax.plot(
        [0.0, 0.0],
        [0.0, 0.0],
        [-polar_axis_extent_km, polar_axis_extent_km],
        color="tab:blue",
        linestyle=":",
        linewidth=1.5,
        label="Earth polar axis",
    )
    polar_axis_label_offset_km = 0.03 * polar_axis_extent_km
    ax.text(
        0.0,
        0.0,
        polar_axis_extent_km + polar_axis_label_offset_km,
        "N",
        color="tab:blue",
        ha="center",
        va="bottom",
    )
    ax.text(
        0.0,
        0.0,
        -polar_axis_extent_km - polar_axis_label_offset_km,
        "S",
        color="tab:blue",
        ha="center",
        va="top",
    )

    (trajectory_line,) = ax.plot(
        [],
        [],
        [],
        color="tab:red",
        label=f"{satellite_name} trajectory",
    )
    moving_satellite_marker = ax.scatter(
        [],
        [],
        [],
        color="tab:orange",
        s=22,
        label="current",
    )
    ax.scatter(
        positions_km[0, 0],
        positions_km[0, 1],
        positions_km[0, 2],
        color="tab:green",
        s=20,
        label="start",
    )
    ax.scatter(
        positions_km[-1, 0],
        positions_km[-1, 1],
        positions_km[-1, 2],
        color="tab:purple",
        s=20,
        label="end",
    )

    max_extent_km = (
        max(
            np.max(np.abs(positions_km)),
            EARTH_MEAN_RADIUS_KM,
            polar_axis_extent_km + polar_axis_label_offset_km,
        )
        * 1.05
    )
    ax.set_xlim(-max_extent_km, max_extent_km)
    ax.set_ylim(-max_extent_km, max_extent_km)
    ax.set_zlim(-max_extent_km, max_extent_km)
    ax.set_box_aspect((1.0, 1.0, 1.0))

    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_zlabel("Z [km]")
    ax.set_title(f"3D animated position history of {satellite_name} around Earth")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.22, 1.0))

    sample_count = positions_km.shape[0]
    max_animation_frames = 1000
    if sample_count > max_animation_frames:
        frame_indices = np.linspace(
            0,
            sample_count - 1,
            num=max_animation_frames,
            dtype=int,
        )
    else:
        frame_indices = np.arange(sample_count)

    def initialize_animation():
        trajectory_line.set_data([], [])
        trajectory_line.set_3d_properties([])
        moving_satellite_marker._offsets3d = ([], [], [])
        return trajectory_line, moving_satellite_marker

    def update_animation(frame_number):
        sample_index = frame_indices[frame_number]
        visible_positions_km = positions_km[: sample_index + 1]

        trajectory_line.set_data(
            visible_positions_km[:, 0],
            visible_positions_km[:, 1],
        )
        trajectory_line.set_3d_properties(visible_positions_km[:, 2])

        moving_satellite_marker._offsets3d = (
            [positions_km[sample_index, 0]],
            [positions_km[sample_index, 1]],
            [positions_km[sample_index, 2]],
        )
        return trajectory_line, moving_satellite_marker

    return FuncAnimation(
        fig,
        update_animation,
        frames=len(frame_indices),
        init_func=initialize_animation,
        interval=10,
        blit=False,
        repeat=True,
    )


def plot_satellite_relative_position_history_3d(
    data: CsvDependentVariableData, satellite_name: str
) -> FuncAnimation | None:
    """Create 3D animated plot of satellite relative position.

    Parameters
    ----------
    data : CsvDependentVariableData
        The loaded CSV data.
    satellite_name : str
        Name of the satellite for labels.

    Returns
    -------
    FuncAnimation | None
        Animation object, or None if no position data available.
    """
    positions_m = _extract_relative_position(data, satellite_name)
    if positions_m.size == 0:
        return None
    positions_km = positions_m / KILOMETERS_TO_METERS

    fig = plt.figure(figsize=PLOT_STANDARD_FIGURE_SIZE_IN)
    ax = fig.add_subplot(111, projection="3d")

    azimuth = np.linspace(0.0, 2.0 * np.pi, 60)
    polar = np.linspace(0.0, np.pi, 30)
    earth_x = EARTH_MEAN_RADIUS_KM * np.outer(np.cos(azimuth), np.sin(polar))
    earth_y = EARTH_MEAN_RADIUS_KM * np.outer(np.sin(azimuth), np.sin(polar))
    earth_z = EARTH_MEAN_RADIUS_KM * np.outer(np.ones_like(azimuth), np.cos(polar))
    ax.plot_surface(earth_x, earth_y, earth_z, color="lightskyblue", alpha=0.35)

    polar_axis_extent_km = 1.5 * EARTH_MEAN_RADIUS_KM
    ax.plot(
        [0.0, 0.0],
        [0.0, 0.0],
        [-polar_axis_extent_km, polar_axis_extent_km],
        color="tab:blue",
        linestyle=":",
        linewidth=1.5,
        label="Earth polar axis",
    )
    polar_axis_label_offset_km = 0.03 * polar_axis_extent_km
    ax.text(
        0.0,
        0.0,
        polar_axis_extent_km + polar_axis_label_offset_km,
        "N",
        color="tab:blue",
        ha="center",
        va="bottom",
    )
    ax.text(
        0.0,
        0.0,
        -polar_axis_extent_km - polar_axis_label_offset_km,
        "S",
        color="tab:blue",
        ha="center",
        va="top",
    )

    (trajectory_line,) = ax.plot(
        [],
        [],
        [],
        color="tab:red",
        label=f"{satellite_name} trajectory",
    )
    moving_satellite_marker = ax.scatter(
        [],
        [],
        [],
        color="tab:orange",
        s=22,
        label="current",
    )
    ax.scatter(
        positions_km[0, 0],
        positions_km[0, 1],
        positions_km[0, 2],
        color="tab:green",
        s=20,
        label="start",
    )
    ax.scatter(
        positions_km[-1, 0],
        positions_km[-1, 1],
        positions_km[-1, 2],
        color="tab:purple",
        s=20,
        label="end",
    )

    max_extent_km = (
        max(
            np.max(np.abs(positions_km)),
            EARTH_MEAN_RADIUS_KM,
            polar_axis_extent_km + polar_axis_label_offset_km,
        )
        * 1.05
    )
    ax.set_xlim(-max_extent_km, max_extent_km)
    ax.set_ylim(-max_extent_km, max_extent_km)
    ax.set_zlim(-max_extent_km, max_extent_km)
    ax.set_box_aspect((1.0, 1.0, 1.0))

    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_zlabel("Z [km]")
    ax.set_title(
        f"3D animated relative position history of {satellite_name} around Earth"
    )
    ax.legend(loc="upper left", bbox_to_anchor=(-0.22, 1.0))

    sample_count = positions_km.shape[0]
    max_animation_frames = 1000
    if sample_count > max_animation_frames:
        frame_indices = np.linspace(
            0,
            sample_count - 1,
            num=max_animation_frames,
            dtype=int,
        )
    else:
        frame_indices = np.arange(sample_count)

    def initialize_animation():
        trajectory_line.set_data([], [])
        trajectory_line.set_3d_properties([])
        moving_satellite_marker._offsets3d = ([], [], [])
        return trajectory_line, moving_satellite_marker

    def update_animation(frame_number):
        sample_index = frame_indices[frame_number]
        visible_positions_km = positions_km[: sample_index + 1]

        trajectory_line.set_data(
            visible_positions_km[:, 0],
            visible_positions_km[:, 1],
        )
        trajectory_line.set_3d_properties(visible_positions_km[:, 2])

        moving_satellite_marker._offsets3d = (
            [positions_km[sample_index, 0]],
            [positions_km[sample_index, 1]],
            [positions_km[sample_index, 2]],
        )
        return trajectory_line, moving_satellite_marker

    return FuncAnimation(
        fig,
        update_animation,
        frames=len(frame_indices),
        init_func=initialize_animation,
        interval=10,
        blit=False,
        repeat=True,
    )


# ===================================================================
# Main entry point
# ===================================================================


def plot_dependent_variables_from_csv(
    dep_var_csv_path: str | Path,
    satellite_name: str,
    show: bool = True,
    duration_s: float | None = None,
) -> list[FuncAnimation | None]:
    """Generate all dependent-variable plots from a CSV file.

    Parameters
    ----------
    dep_var_csv_path : str | Path
        Path to the dependent-variable CSV file.
    satellite_name : str
        Name of the satellite for filtering and labels.
    show : bool, optional
        Whether to display plots (default: True).
    duration_s : float | None, optional
        Duration in seconds to plot. If None, plots all data (default: None).

    Returns
    -------
    list[FuncAnimation | None]
        List of animation objects for 3D trajectory plots.

    Raises
    ------
    ValueError
        If the CSV file has no data rows.
    """
    data = load_csv_dependent_variable_data(dep_var_csv_path)
    if data.time_history_tdb_s.size == 0:
        raise ValueError("loaded dependent-variable CSV has no data rows for plotting")

    # Auto-detect satellite name if the provided name doesn't match any data
    if satellite_name == "Satellite" and data.metadata:
        # Try to find a satellite name from the metadata
        for meta in data.metadata:
            if meta.associated_body and meta.associated_body != "Earth":
                satellite_name = meta.associated_body
                break

    relative_time_h = (
        data.time_history_tdb_s - data.time_history_tdb_s[0]
    ) / SECONDS_PER_HOUR

    # Filter data by duration if specified
    if duration_s is not None:
        duration_h = duration_s / SECONDS_PER_HOUR
        mask = relative_time_h <= duration_h
        relative_time_h = relative_time_h[mask]

        # Create a filtered copy of data with only the selected time range
        filtered_data = CsvDependentVariableData(
            time_history_tdb_s=data.time_history_tdb_s[mask],
            dep_var_columns={
                key: values[mask] for key, values in data.dep_var_columns.items()
            },
            metadata=data.metadata,
        )
        data = filtered_data

    plot_total_acceleration(data, relative_time_h, satellite_name)
    plot_ground_track(data, relative_time_h, satellite_name)
    plot_kepler_elements(data, relative_time_h, satellite_name)
    plot_acceleration_components(data, relative_time_h, satellite_name)
    trajectory_animation = []
    trajectory_animation.append(
        plot_satellite_body_fixed_position_history_3d(data, satellite_name)
    )
    trajectory_animation.append(
        plot_satellite_relative_position_history_3d(data, satellite_name)
    )

    if show:
        plt.show()

    return trajectory_animation


def build_cli_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Plot dependent-variable histories from a saved Tudat CSV file."
    )
    parser.add_argument(
        "dep_vars_csv",
        metavar="<dep_vars_csv>",
        help="Path to *_dep_vars.csv produced by propagate_orbit.py",
    )
    parser.add_argument(
        "--name",
        default="Satellite",
        metavar="<name>",
        help="Satellite name used in labels and header filtering (default: Satellite).",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=time_utils.parse_duration_to_seconds,
        default=None,
        metavar="<duration>",
        help="Duration to plot in format <number>[s|m|h|d] (e.g., 1h, 30m, 3600s). If not specified, plots all data.",
    )
    return parser


def main() -> None:
    """Main entry point for the script."""
    cli_args = build_cli_parser().parse_args()

    # Keep animation objects alive until plt.show() returns.
    animations: list[FuncAnimation] = []

    if cli_args.dep_vars_csv is not None:
        dep_var_animation = plot_dependent_variables_from_csv(
            dep_var_csv_path=cli_args.dep_vars_csv,
            satellite_name=cli_args.name,
            show=False,
            duration_s=cli_args.duration,
        )
        if dep_var_animation is not None:
            animations.append(dep_var_animation)

    plt.show()


if __name__ == "__main__":
    main()
