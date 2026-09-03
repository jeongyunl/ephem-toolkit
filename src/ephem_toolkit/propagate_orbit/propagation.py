"""Core propagation logic for orbit propagation.

This module provides the main propagation execution function that coordinates
environment setup, acceleration models, propagator configuration, and output
generation for orbital dynamics simulations.
"""

from __future__ import annotations

import sys

from ephem_toolkit.core.propagator.base import OutputMode
from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagator,
    NumericalPropagatorConfig,
)

from .output_handling import write_dependent_variables_csv, write_state_history_oem


def run_propagation(
    config: NumericalPropagatorConfig,
    initial_state: NumericalInitialState,
    target_epoch_s: float,
    output_oem_path: str,
    output_dep_vars_path: str | None,
    data_only: bool,
) -> None:
    """Run the orbit propagation and write outputs.

    Parameters
    ----------
    config : NumericalPropagatorConfig
        Force-model and integrator configuration.
    initial_state : NumericalInitialState
        Initial Cartesian state and epoch.
    target_epoch_s : float
        Propagation end epoch (TT, s since J2000 TT).
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
    propagator = NumericalPropagator(config, initial_state)
    trajectory = propagator.propagate_to(target_epoch_s, output=OutputMode.TRAJECTORY)
    if trajectory is None:
        raise RuntimeError("Propagation did not produce a trajectory.")

    state_history = {epoch_s: state for epoch_s, state in trajectory}
    dep_var_dict = propagator.dependent_variable_dictionary
    dependent_variables_to_save = propagator.dependent_variable_save_settings
    if dep_var_dict is None or dependent_variables_to_save is None:
        raise RuntimeError(
            "Propagation output did not retain dependent-variable metadata."
        )

    try:
        write_state_history_oem(
            state_history,
            output_oem_path,
            config,
            data_only,
        )
    except OSError as exc:
        print(f"Error: failed to write OEM output: {exc}", file=sys.stderr)
        sys.exit(1)

    if output_dep_vars_path is not None:
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
