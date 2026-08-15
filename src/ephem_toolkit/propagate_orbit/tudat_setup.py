"""Tudat environment and model setup for orbit propagation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import ephem_toolkit.core.spice_utils as spice_utils
import ephem_toolkit.core.time_utils as time_utils
from tudatpy.dynamics import environment_setup, propagation_setup
from tudatpy.dynamics.propagation_setup import dependent_variable

from .constants import (
    DEFAULT_BODIES_TO_CREATE,
    DEFAULT_GLOBAL_FRAME_ORIENTATION,
    DEFAULT_GLOBAL_FRAME_ORIGIN,
    DEFAULT_INTEGRATOR_METHOD,
    SUPPORTED_INTEGRATOR_METHODS,
)
from .data_structures import PropagationInputs


def load_spice_kernels() -> None:
    """Load required SPICE kernels for propagation support.

    Kernels are loaded from Tudat's managed kernel directory.
    """
    spice_kernel_files = [
        "naif0012.tls",  # Leapseconds kernel file
        "pck00011.tpc",  # Planetary constants: orientation and size/shape data for natural bodies (Sun, planets, asteroids, etc.)
        "gm_de431.tpc",  # Planetary constants: gravitational parameters for natural bodies
        "earth_200101_990825_predict.bpc",  # Earth rotation prediction (Jan 2001 to Aug 2099)
        "tudat_merged_spk_kernel.bsp",  # Merged SPK kernel containing ephemerides for Earth, Sun, Moon, Mars, Venus
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


def create_environment_and_bodies(propagation_inputs: PropagationInputs) -> Any:
    """Create environment settings, add spacecraft interfaces, and build bodies.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.

    Returns
    -------
    object
        Tudat system-of-bodies object.

    Notes
    -----
    Sun and Earth are always present. Moon, Mars, and Venus are included only
    when their corresponding gravity flags are enabled. The spacecraft drag area
    is reused as the cannonball reference area for SRP.
    """
    # Build the list of celestial bodies dynamically. Sun and Earth are always
    # required; Moon, Mars, and Venus are only included when their respective
    # gravity perturbation is enabled.
    bodies_to_create = list(DEFAULT_BODIES_TO_CREATE)
    if propagation_inputs.is_moon_gravity_on:
        bodies_to_create.append("Moon")
    if propagation_inputs.is_mars_gravity_on:
        bodies_to_create.append("Mars")
    if propagation_inputs.is_venus_gravity_on:
        bodies_to_create.append("Venus")

    body_settings = environment_setup.get_default_body_settings(
        bodies_to_create,
        DEFAULT_GLOBAL_FRAME_ORIGIN,
        DEFAULT_GLOBAL_FRAME_ORIENTATION,
    )

    # Add the satellite as an empty body, then attach force-model interfaces based on enabled options.
    body_settings.add_empty_settings(propagation_inputs.satellite_name)

    # Only attach radiation pressure target settings when SRP is enabled.
    if propagation_inputs.is_srp_on:
        occulting_bodies_dict = {"Sun": ["Earth"]}
        vehicle_target_settings = (
            environment_setup.radiation_pressure.cannonball_radiation_target(
                propagation_inputs.satellite_drag_area_m2,
                propagation_inputs.srp_coefficient,
                occulting_bodies_dict,
            )
        )
        body_settings.get(
            propagation_inputs.satellite_name
        ).radiation_pressure_target_settings = vehicle_target_settings

    # Only attach aerodynamic coefficient settings when drag is enabled.
    if propagation_inputs.is_earth_drag_on:
        aero_coefficient_settings = environment_setup.aerodynamic_coefficients.constant(
            propagation_inputs.satellite_drag_area_m2,
            [propagation_inputs.satellite_drag_coefficient, 0.0, 0.0],
        )
        body_settings.get(
            propagation_inputs.satellite_name
        ).aerodynamic_coefficient_settings = aero_coefficient_settings

    bodies = environment_setup.create_system_of_bodies(body_settings)
    bodies.get(propagation_inputs.satellite_name).mass = (
        propagation_inputs.satellite_mass_kg
    )
    return bodies


def create_acceleration_models(
    propagation_inputs: PropagationInputs,
    bodies: Any,
    bodies_to_propagate: list[str],
    central_bodies: list[str],
) -> Any:
    """Create acceleration models for the propagated satellite.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    bodies : object
        Tudat system-of-bodies object.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    central_bodies : list[str]
        Central bodies for translational dynamics.

    Returns
    -------
    object
        Tudat acceleration-model map.

    Notes
    -----
    The model always includes Earth spherical-harmonic gravity and conditionally
    includes drag, SRP, and third-body point-mass perturbations according to
    CLI-derived flags.
    """
    satellite_acceleration_settings = {}

    # Sun accelerations: radiation pressure and/or point-mass gravity.
    sun_accelerations = []
    if propagation_inputs.is_srp_on:
        sun_accelerations.insert(0, propagation_setup.acceleration.radiation_pressure())
    if propagation_inputs.is_sun_gravity_on:
        sun_accelerations.append(propagation_setup.acceleration.point_mass_gravity())

    if sun_accelerations:
        satellite_acceleration_settings["Sun"] = sun_accelerations

    # Include aerodynamic drag acceleration from Earth only when drag is enabled.
    earth_accelerations = [
        propagation_setup.acceleration.spherical_harmonic_gravity(
            propagation_inputs.earth_spherical_harmonic_gravity_degree,
            propagation_inputs.earth_spherical_harmonic_gravity_order,
        ),
    ]
    if propagation_inputs.is_earth_drag_on:
        earth_accelerations.append(propagation_setup.acceleration.aerodynamic())
    satellite_acceleration_settings["Earth"] = earth_accelerations

    # Include Moon point-mass gravity only when enabled.
    if propagation_inputs.is_moon_gravity_on:
        satellite_acceleration_settings["Moon"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # Include Venus point-mass gravity only when enabled.
    if propagation_inputs.is_venus_gravity_on:
        satellite_acceleration_settings["Venus"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # Include Mars point-mass gravity only when enabled.
    if propagation_inputs.is_mars_gravity_on:
        satellite_acceleration_settings["Mars"] = [
            propagation_setup.acceleration.point_mass_gravity()
        ]

    # Create global accelerations settings dictionary.
    acceleration_settings = {
        propagation_inputs.satellite_name: satellite_acceleration_settings
    }

    return propagation_setup.create_acceleration_models(
        bodies, acceleration_settings, bodies_to_propagate, central_bodies
    )


def create_dependent_variables_to_save(
    propagation_inputs: PropagationInputs,
) -> list[Any]:
    """Create dependent-variable save settings for propagation and plotting.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.

    Returns
    -------
    list[Any]
        Dependent-variable save settings passed to the propagator and reused
        later for plotting.
    """
    dependent_variables_to_save = [
        dependent_variable.total_acceleration(propagation_inputs.satellite_name),
        dependent_variable.keplerian_state(propagation_inputs.satellite_name, "Earth"),
        dependent_variable.geodetic_latitude(
            propagation_inputs.satellite_name, "Earth"
        ),
        dependent_variable.longitude(propagation_inputs.satellite_name, "Earth"),
        dependent_variable.central_body_fixed_cartesian_position(
            propagation_inputs.satellite_name, "Earth"
        ),
        dependent_variable.relative_position(
            propagation_inputs.satellite_name, "Earth"
        ),
    ]

    # Earth spherical harmonic gravity is always tracked; other norms are added conditionally.
    dependent_variables_to_save.append(
        dependent_variable.single_acceleration_norm(
            propagation_setup.acceleration.spherical_harmonic_gravity_type,
            propagation_inputs.satellite_name,
            "Earth",
        ),
    )

    # Track Moon gravity acceleration norm only when enabled.
    if propagation_inputs.is_moon_gravity_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Moon",
            ),
        )

    # Track Sun gravity acceleration norm only when enabled.
    if propagation_inputs.is_sun_gravity_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Sun",
            ),
        )

    # Track SRP acceleration norm only when SRP is enabled.
    if propagation_inputs.is_srp_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.radiation_pressure_type,
                propagation_inputs.satellite_name,
                "Sun",
            ),
        )

    # Track aerodynamic drag acceleration norm only when enabled.
    if propagation_inputs.is_earth_drag_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.aerodynamic_type,
                propagation_inputs.satellite_name,
                "Earth",
            ),
        )

    # Track Venus gravity acceleration norm only when enabled.
    if propagation_inputs.is_venus_gravity_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Venus",
            ),
        )

    # Track Mars gravity acceleration norm only when enabled.
    if propagation_inputs.is_mars_gravity_on:
        dependent_variables_to_save.append(
            dependent_variable.single_acceleration_norm(
                propagation_setup.acceleration.point_mass_gravity_type,
                propagation_inputs.satellite_name,
                "Mars",
            ),
        )

    return dependent_variables_to_save


def create_translational_propagator_settings(
    propagation_inputs: PropagationInputs,
    central_bodies: list[str],
    acceleration_models: Any,
    bodies_to_propagate: list[str],
    dependent_variables_to_save: list[Any],
) -> Any:
    """Create translational propagator settings for the configured run.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation options.
    central_bodies : list[str]
        Central bodies for translational dynamics.
    acceleration_models : object
        Acceleration model map returned by Tudat setup utilities.
    bodies_to_propagate : list[str]
        Bodies whose translational states are propagated.
    dependent_variables_to_save : list[Any]
        Dependent-variable save settings passed to the propagator.

    Returns
    -------
    object
        Tudat translational propagator settings object.

    Notes
    -----
    Fixed-step integration is selected when one step-size value is provided.
    Variable-step integration is selected when three values are provided and
    uses element-wise scalar tolerances of ``1e-10`` for both absolute and
    relative error control.
    """
    # Resolve the CoefficientSets entry by integrator method name.
    try:
        coefficient_set = getattr(
            propagation_setup.integrator.CoefficientSets,
            propagation_inputs.integrator_method,
        )
    except AttributeError as exc:
        raise ValueError(
            "Unsupported integrator method "
            f"'{propagation_inputs.integrator_method}'. Supported methods are: "
            f"{', '.join(SUPPORTED_INTEGRATOR_METHODS)}. "
            f"Default is {DEFAULT_INTEGRATOR_METHOD}."
        ) from exc

    # Configure fixed-step or variable-step integrator based on the number of step-size values.
    if len(propagation_inputs.integrator_step_size_values_s) == 1:
        fixed_step_size_s = propagation_inputs.integrator_step_size_values_s[0]
        integrator_settings = propagation_setup.integrator.runge_kutta_fixed_step(
            fixed_step_size_s,
            coefficient_set=coefficient_set,
        )
    else:
        (
            initial_step_size_s,
            minimum_step_size_s,
            maximum_step_size_s,
        ) = propagation_inputs.integrator_step_size_values_s

        step_size_validation_settings = (
            propagation_setup.integrator.step_size_validation(
                minimum_step_size_s, maximum_step_size_s
            )
        )

        step_size_control_settings = (
            propagation_setup.integrator.step_size_control_elementwise_scalar_tolerance(
                1.0e-10, 1.0e-10
            )
        )

        integrator_settings = propagation_setup.integrator.runge_kutta_variable_step(
            initial_time_step=initial_step_size_s,
            coefficient_set=coefficient_set,
            step_size_validation_settings=step_size_validation_settings,
            step_size_control_settings=step_size_control_settings,
        )

    simulation_end_epoch_datetime_utc = (
        propagation_inputs.initial_epoch_datetime_utc
        + timedelta(seconds=propagation_inputs.simulation_duration_s)
    )
    termination_condition = propagation_setup.propagator.time_termination(
        time_utils.datetime_to_tdb_s(simulation_end_epoch_datetime_utc)
    )

    return propagation_setup.propagator.translational(
        central_bodies,
        acceleration_models,
        bodies_to_propagate,
        propagation_inputs.initial_state_m_m_s,
        time_utils.datetime_to_tdb_s(propagation_inputs.initial_epoch_datetime_utc),
        integrator_settings,
        termination_condition,
        output_variables=dependent_variables_to_save,
    )
