"""Core propagation logic for orbit propagation.

This module provides the main propagation execution function that coordinates
environment setup, acceleration models, propagator configuration, and output
generation for orbital dynamics simulations.
"""

from __future__ import annotations

import sys
from typing import Any

from tudatpy.dynamics import propagation, simulator

from . import tudat_setup
from .data_structures import PropagationInputs
from .output_handling import write_dependent_variables_csv, write_state_history_oem


def run_propagation(
    propagation_inputs: PropagationInputs,
    output_oem_path: str,
    output_dep_vars_path: str | None,
    data_only: bool,
) -> None:
    """Run the orbit propagation and write outputs.

    Parameters
    ----------
    propagation_inputs : PropagationInputs
        Consolidated propagation configuration.
    output_oem_path : str
        Path to write OEM output, or '-' for stdout.
    output_dep_vars_path : str | None
        Path to write dependent variables CSV, or None to skip.
    data_only : bool
        Whether to write only OEM data without header/metadata.

    Returns
    -------
    None
        Writes outputs to specified paths and may exit on error.
    """
    bodies = tudat_setup.create_environment_and_bodies(propagation_inputs)

    bodies_to_propagate = [propagation_inputs.satellite_name]
    central_bodies = ["Earth"]

    acceleration_models = tudat_setup.create_acceleration_models(
        propagation_inputs=propagation_inputs,
        bodies=bodies,
        bodies_to_propagate=bodies_to_propagate,
        central_bodies=central_bodies,
    )

    dependent_variables_to_save = tudat_setup.create_dependent_variables_to_save(
        propagation_inputs
    )

    propagator_settings = tudat_setup.create_translational_propagator_settings(
        propagation_inputs=propagation_inputs,
        central_bodies=central_bodies,
        acceleration_models=acceleration_models,
        bodies_to_propagate=bodies_to_propagate,
        dependent_variables_to_save=dependent_variables_to_save,
    )

    dynamics_simulator = simulator.create_dynamics_simulator(
        bodies, propagator_settings
    )

    state_history = dynamics_simulator.propagation_results.state_history
    try:
        write_state_history_oem(
            state_history,
            output_oem_path,
            propagation_inputs,
            data_only,
        )
    except OSError as exc:
        print(f"Error: failed to write OEM output: {exc}", file=sys.stderr)
        sys.exit(1)

    if output_dep_vars_path is not None:
        dep_var_dict = propagation.create_dependent_variable_dictionary(
            dynamics_simulator
        )
        try:
            write_dependent_variables_csv(
                output_dep_vars_path,
                dep_var_dict,
                dependent_variables_to_save,
            )
            print(f"Dependent variables saved to: {output_dep_vars_path}")
        except OSError as exc:
            print(
                f"Error: failed to write dependent variables CSV: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
