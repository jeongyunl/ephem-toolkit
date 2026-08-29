"""Output handling for orbit propagation results."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

import ephem_toolkit.core.ccsds.oem as common_oem
import ephem_toolkit.core.time_utils as time_utils

from .constants import (
    DEFAULT_GLOBAL_FRAME_ORIENTATION,
    DEFAULT_GLOBAL_FRAME_ORIGIN,
    INTEGRATOR_METHOD_DESCRIPTIONS,
    KILOMETERS_TO_METERS,
)
from .data_structures import PropagationInputs


def write_state_history_oem(
    state_history: dict[float, np.ndarray],
    dest: str,
    propagation_inputs: PropagationInputs,
    data_only: bool,
) -> None:
    """Write propagated state history in OEM or data-only format.

    Parameters
    ----------
    state_history : dict[float, numpy.ndarray]
        Mapping of TDB seconds since J2000 to 6-element cartesian state vectors
        in SI units ``[x, y, z, vx, vy, vz]``.
    dest : str
        Output file path, or ``'-'`` to write to stdout.
    propagation_inputs : PropagationInputs
        Propagation configuration used to populate OEM metadata.
    data_only : bool
        Whether to write only state-vector data without OEM header or metadata.

    Returns
    -------
    None
        Writes a complete OEM message to the specified destination unless
        ``data_only`` is true, in which case only ``UTC_ISO x y z vx vy vz``
        state records are written in km and km/s.
    """
    if dest == "-":
        stream = sys.stdout
        should_close = False
    else:
        stream = open(dest, "w", encoding="utf-8")
        should_close = True

    try:
        # TT ≈ TDB (< 2ms); pass TDB values directly as TT seconds since J2000
        oem_states = [
            (epoch_tdb_s, state_m_m_s)
            for epoch_tdb_s, state_m_m_s in state_history.items()
        ]
        oem = common_oem.CcsdsOem.from_states(
            oem_states,
            object_name=propagation_inputs.satellite_name,
            ref_frame=DEFAULT_GLOBAL_FRAME_ORIENTATION,
            center_name=DEFAULT_GLOBAL_FRAME_ORIGIN,
            time_system="UTC",
        )

        if data_only:
            oem.write_states(stream)
        else:
            oem.write(stream)

    finally:
        if should_close:
            stream.close()


def build_dependent_variable_csv_header_prefix(dep_var_setting: Any) -> str:
    """Build the dependent-variable CSV header prefix for one setting.

    Parameters
    ----------
    dep_var_setting : Any
        Tudat dependent-variable save setting.

    Returns
    -------
    str
        Header prefix in the format
        ``dep_var_type/acceleration_model_type/associated_body/secondary_body/component_index``.
    """
    dep_var_type_name = dep_var_setting.dependent_variable_type.name.removesuffix(
        "_type"
    )

    acceleration_model_type = ""
    if hasattr(dep_var_setting, "acceleration_model_type"):
        acceleration_model_type = (
            dep_var_setting.acceleration_model_type.name.removesuffix("_type")
        )

    associated_body = ""
    if dep_var_setting.associated_body is not None and dep_var_setting.associated_body:
        associated_body = dep_var_setting.associated_body

    secondary_body = ""
    if dep_var_setting.secondary_body is not None and dep_var_setting.secondary_body:
        secondary_body = dep_var_setting.secondary_body

    component_index = ""
    if dep_var_setting.component_index >= 0:
        component_index = str(dep_var_setting.component_index)

    return (
        f"{dep_var_type_name}/{acceleration_model_type}/"
        f"{associated_body}/{secondary_body}/{component_index}"
    )


def write_dependent_variables_csv(
    dep_var_csv_path: str,
    dep_var_dict: Any,
    dependent_variables_to_save: list[Any],
) -> None:
    """Write dependent variables to a CSV file.

    Parameters
    ----------
    dep_var_csv_path : str
        Path to the output CSV file.
    dep_var_dict : Any
        Tudat dependent variable dictionary.
    dependent_variables_to_save : list[Any]
        List of dependent variable settings.

    Returns
    -------
    None
        Writes dependent variables to the specified CSV file.
    """
    # Build header row using the dependent_variable_type enum name for each saved variable.
    # Each dependent variable may be multi-dimensional (e.g., vectors have 3 components,
    # Keplerian state has 6). We expand the header accordingly.
    headers = ["epoch_tt_s"]
    for dep_var_setting in dependent_variables_to_save:
        header = build_dependent_variable_csv_header_prefix(dep_var_setting)

        # Multi-column expansion for vector/array dependent variables
        dep_var_array = dep_var_dict.asarray(dep_var_setting)
        if dep_var_array.ndim == 1 or (
            dep_var_array.ndim == 2 and dep_var_array.shape[1] == 1
        ):
            headers.append(header + "/")
        else:
            n_cols = dep_var_array.shape[1]
            for col_idx in range(n_cols):
                headers.append(f"{header}/{col_idx}")

    # Write CSV rows
    time_history = dep_var_dict.time_history
    with open(dep_var_csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        for row_idx, epoch_tt_s in enumerate(time_history):
            row = [epoch_tt_s]
            for dep_var_setting in dependent_variables_to_save:
                dep_var_array = dep_var_dict.asarray(dep_var_setting)
                if dep_var_array.ndim == 1 or (
                    dep_var_array.ndim == 2 and dep_var_array.shape[1] == 1
                ):
                    row.append(
                        float(dep_var_array[row_idx])
                        if dep_var_array.ndim == 1
                        else float(dep_var_array[row_idx, 0])
                    )
                else:
                    for col_idx in range(dep_var_array.shape[1]):
                        row.append(float(dep_var_array[row_idx, col_idx]))
            writer.writerow(row)


def print_pre_propagation_summary(
    propagation_inputs: PropagationInputs,
    input_source: str,
    output_oem_path: str | None = None,
    dep_var_csv_path: str | None = None,
) -> None:
    """Print the pre-propagation configuration summary.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    input_source : str
        Input source label displayed to the user.
    output_oem_path : str | None, optional
        OEM state-history output destination. Use ``'-'`` for stdout.
    dep_var_csv_path : str | None, optional
        Dependent-variable CSV output destination.

    Returns
    -------
    None
        Prints a formatted summary to stdout.
    """

    print("=== Propagation Configuration ===")
    print(f"Input source: {input_source}")
    print(f"Satellite name: {propagation_inputs.satellite_name}")
    print(f"Satellite mass [kg]: {propagation_inputs.satellite_mass_kg}")

    # Display integrator method and step size(s), with mode (fixed or variable)
    # inferred from the number of step size values provided
    integrator_description = INTEGRATOR_METHOD_DESCRIPTIONS.get(
        propagation_inputs.integrator_method, "unknown method"
    )
    print(
        "Integrator method: "
        f"{propagation_inputs.integrator_method} ({integrator_description})"
    )
    if len(propagation_inputs.integrator_step_size_values_s) == 1:
        print("Integrator mode: fixed-step size")
        print(
            "Integrator step size [s]: "
            f"{propagation_inputs.integrator_step_size_values_s[0]}"
        )
    else:
        print("Integrator mode: variable-step size")
        (
            initial_step_size_s,
            minimum_step_size_s,
            maximum_step_size_s,
        ) = propagation_inputs.integrator_step_size_values_s
        print(
            "Integrator step sizes [s] "
            f"(initial, minimum, maximum): {initial_step_size_s}, "
            f"{minimum_step_size_s}, {maximum_step_size_s}"
        )

    print(
        "Earth spherical harmonic gravity [degree x order]: "
        f"{propagation_inputs.earth_spherical_harmonic_gravity_degree}x"
        f"{propagation_inputs.earth_spherical_harmonic_gravity_order}"
    )

    # Display drag area, which is used for both drag and SRP
    print(f"Drag area [m²]: {propagation_inputs.satellite_drag_area_m2}")

    # Display SRP status; only show coefficient when SRP is enabled
    print(
        f"Solar radiation pressure: {'on' if propagation_inputs.is_srp_on else 'off'}"
    )
    if propagation_inputs.is_srp_on:
        print(
            f"Solar radiation pressure coefficient: {propagation_inputs.srp_coefficient}"
        )

    # Display drag status; only show coefficient when drag is enabled
    print(f"Aerodynamic drag: {'on' if propagation_inputs.is_earth_drag_on else 'off'}")
    if propagation_inputs.is_earth_drag_on:
        print(f"Drag coefficient: {propagation_inputs.satellite_drag_coefficient}")

    # Display third-body gravity status
    print(f"Moon gravity: {'on' if propagation_inputs.is_moon_gravity_on else 'off'}")
    print(f"Sun gravity: {'on' if propagation_inputs.is_sun_gravity_on else 'off'}")
    print(f"Venus gravity: {'on' if propagation_inputs.is_venus_gravity_on else 'off'}")
    print(f"Mars gravity: {'on' if propagation_inputs.is_mars_gravity_on else 'off'}")

    print(
        f"Initial epoch: {time_utils.datetime_to_iso8601(propagation_inputs.initial_epoch_datetime_utc)}"
    )
    initial_position_km = (
        propagation_inputs.initial_state_m_m_s[:3] / KILOMETERS_TO_METERS
    )
    initial_velocity_km_s = (
        propagation_inputs.initial_state_m_m_s[3:] / KILOMETERS_TO_METERS
    )
    print(
        "Initial position vector [km]: "
        f"{np.array2string(initial_position_km, precision=6, separator=', ')}"
    )
    print(
        "Initial velocity vector [km/s]: "
        f"{np.array2string(initial_velocity_km_s, precision=6, separator=', ')}"
    )
    print(f"Simulation duration [s]: {propagation_inputs.simulation_duration_s}")
    simulation_end_epoch_datetime_utc = (
        propagation_inputs.initial_epoch_datetime_utc
        + timedelta(seconds=propagation_inputs.simulation_duration_s)
    )
    print(
        "Simulation end epoch: "
        f"{time_utils.datetime_to_iso8601(simulation_end_epoch_datetime_utc)}"
    )
    if output_oem_path is not None:
        output_destination = "stdout" if output_oem_path == "-" else output_oem_path
        print(f"OEM output: {output_destination}")
    if dep_var_csv_path is not None:
        print(f"Dependent variables CSV output: {dep_var_csv_path}")
    print("=================================")
