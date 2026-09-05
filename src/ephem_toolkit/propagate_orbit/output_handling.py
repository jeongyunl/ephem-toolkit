"""Output handling for orbit propagation results."""

from __future__ import annotations

import csv
import sys
from typing import Any

import numpy as np

import ephem_toolkit.core.ccsds.oem as common_oem
import ephem_toolkit.core.provenance as provenance
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagatorConfig,
)

from ephem_toolkit.core.propagator.numerical import (
    DEFAULT_GLOBAL_FRAME_ORIENTATION,
    DEFAULT_GLOBAL_FRAME_ORIGIN,
    INTEGRATOR_METHOD_DESCRIPTIONS,
)
from .constants import KILOMETERS_TO_METERS


def write_state_history_oem(
    state_history: dict[float, np.ndarray],
    dest: str,
    config: NumericalPropagatorConfig,
    data_only: bool,
) -> None:
    """Write propagated state history in OEM or data-only format.

    Parameters
    ----------
    state_history : dict[float, numpy.ndarray]
        Mapping of TT seconds since J2000 to 6-element Cartesian state vectors
        in SI units ``[x, y, z, vx, vy, vz]``.
    dest : str
        Output file path, or ``'-'`` to write to stdout.
    config : NumericalPropagatorConfig
        Force-model configuration used to populate OEM metadata.
    data_only : bool
        Whether to write only state-vector data without OEM header or metadata.
    """
    if dest == "-":
        stream = sys.stdout
        should_close = False
    else:
        stream = open(dest, "w", encoding="utf-8")
        should_close = True

    try:
        oem_states = list(state_history.items())
        oem = common_oem.CcsdsOem.from_states(
            oem_states,
            object_name=config.satellite_name,
            ref_frame=DEFAULT_GLOBAL_FRAME_ORIENTATION,
            center_name=DEFAULT_GLOBAL_FRAME_ORIGIN,
            time_system="UTC",
        )
        oem.meta.comments.extend(
            [
                provenance.provenance_comment(
                    source="OPM",
                    transformation="propagation",
                    target_model="numerical",
                ),
                (
                    "EPHEMERIS_PROPAGATION: "
                    f"integrator={config.integrator_method}; "
                    f"step_size_s={config.integrator_step_size_values_s}; "
                    f"earth_gravity="
                    f"{config.earth_spherical_harmonic_gravity_degree}x"
                    f"{config.earth_spherical_harmonic_gravity_order}; "
                    f"drag={'on' if config.is_earth_drag_on else 'off'}; "
                    f"srp={'on' if config.is_srp_on else 'off'}; "
                    f"moon={'on' if config.is_moon_gravity_on else 'off'}; "
                    f"sun={'on' if config.is_sun_gravity_on else 'off'}; "
                    f"venus={'on' if config.is_venus_gravity_on else 'off'}; "
                    f"mars={'on' if config.is_mars_gravity_on else 'off'}"
                ),
            ]
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
    """
    headers = ["epoch_tt_s"]
    for dep_var_setting in dependent_variables_to_save:
        header = build_dependent_variable_csv_header_prefix(dep_var_setting)
        dep_var_array = dep_var_dict.asarray(dep_var_setting)
        if dep_var_array.ndim == 1 or (
            dep_var_array.ndim == 2 and dep_var_array.shape[1] == 1
        ):
            headers.append(header + "/")
        else:
            n_cols = dep_var_array.shape[1]
            for col_idx in range(n_cols):
                headers.append(f"{header}/{col_idx}")

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
    config: NumericalPropagatorConfig,
    initial_state: NumericalInitialState,
    target_epoch_s: float,
    input_source: str,
    output_oem_path: str | None = None,
    dep_var_csv_path: str | None = None,
) -> None:
    """Print the pre-propagation configuration summary.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.
    initial_state : NumericalInitialState
        Initial Cartesian state and epoch.
    target_epoch_s : float
        Propagation end epoch (TT, s since J2000 TT).
    input_source : str
        Input source label displayed to the user.
    output_oem_path : str | None, optional
        OEM state-history output destination. Use ``'-'`` for stdout.
    dep_var_csv_path : str | None, optional
        Dependent-variable CSV output destination.
    """
    print("=== Propagation Configuration ===")
    print(f"Input source: {input_source}")
    print(f"Satellite name: {config.satellite_name}")
    print(f"Satellite mass [kg]: {config.satellite_mass_kg}")

    integrator_description = INTEGRATOR_METHOD_DESCRIPTIONS.get(
        config.integrator_method, "unknown method"
    )
    print(f"Integrator method: {config.integrator_method} ({integrator_description})")
    if len(config.integrator_step_size_values_s) == 1:
        print("Integrator mode: fixed-step size")
        print(f"Integrator step size [s]: {config.integrator_step_size_values_s[0]}")
    else:
        initial_step_size_s, minimum_step_size_s, maximum_step_size_s = (
            config.integrator_step_size_values_s
        )
        print("Integrator mode: variable-step size")
        print(
            f"Integrator step sizes [s] (initial, minimum, maximum): "
            f"{initial_step_size_s}, {minimum_step_size_s}, {maximum_step_size_s}"
        )

    print(
        f"Earth spherical harmonic gravity [degree x order]: "
        f"{config.earth_spherical_harmonic_gravity_degree}x"
        f"{config.earth_spherical_harmonic_gravity_order}"
    )
    print(f"Drag area [m²]: {config.satellite_drag_area_m2}")
    print(f"Solar radiation pressure: {'on' if config.is_srp_on else 'off'}")
    if config.is_srp_on:
        print(f"Solar radiation pressure coefficient: {config.srp_coefficient}")
    print(f"Aerodynamic drag: {'on' if config.is_earth_drag_on else 'off'}")
    if config.is_earth_drag_on:
        print(f"Drag coefficient: {config.satellite_drag_coefficient}")
    print(f"Moon gravity: {'on' if config.is_moon_gravity_on else 'off'}")
    print(f"Sun gravity: {'on' if config.is_sun_gravity_on else 'off'}")
    print(f"Venus gravity: {'on' if config.is_venus_gravity_on else 'off'}")
    print(f"Mars gravity: {'on' if config.is_mars_gravity_on else 'off'}")

    initial_epoch_dt = time_utils.tt_s_to_datetime(initial_state.epoch_s)
    print(f"Initial epoch: {time_utils.datetime_to_iso8601(initial_epoch_dt)}")
    initial_position_km = initial_state.state_m_m_s[:3] / KILOMETERS_TO_METERS
    initial_velocity_km_s = initial_state.state_m_m_s[3:] / KILOMETERS_TO_METERS
    print(
        "Initial position vector [km]: "
        f"{np.array2string(initial_position_km, precision=6, separator=', ')}"
    )
    print(
        "Initial velocity vector [km/s]: "
        f"{np.array2string(initial_velocity_km_s, precision=6, separator=', ')}"
    )
    duration_s = target_epoch_s - initial_state.epoch_s
    print(f"Simulation duration [s]: {duration_s}")
    end_epoch_dt = time_utils.tt_s_to_datetime(target_epoch_s)
    print(f"Simulation end epoch: {time_utils.datetime_to_iso8601(end_epoch_dt)}")
    if output_oem_path is not None:
        output_destination = "stdout" if output_oem_path == "-" else output_oem_path
        print(f"OEM output: {output_destination}")
    if dep_var_csv_path is not None:
        print(f"Dependent variables CSV output: {dep_var_csv_path}")
    print("=================================")
