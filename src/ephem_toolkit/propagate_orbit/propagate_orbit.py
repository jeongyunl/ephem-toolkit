#!/usr/bin/env python3
"""Perturbed satellite orbit propagation.

Propagates a (quasi-massless) body dominated by a central point-mass attractor,
including multiple perturbing accelerations from the central body and third bodies
(drag, radiation pressure, spherical-harmonic gravity, and point-mass gravity from
Moon, Sun, Mars, and Venus).

The script expects exactly one OEM-like state line as input with epoch and six
Cartesian components: ``UTC_ISO x y z vx vy vz`` where position is in km and
velocity in km/s. Input is read from ``--initial-state`` when provided, otherwise
from stdin.

Usage:
    propagate-orbit [options]

Only the bare minimum needed for CLI argument parsing (``argparse``, ``re``) is
imported at the top of the file. Every other module — including standard library,
NumPy, and TudatPy — is imported as late as possible, immediately before its
first use. This keeps ``--help`` and argument validation instant and defers heavy
library initialisation until the point where it is actually required.
"""

from __future__ import annotations

import contextlib
import sys
import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)


from . import plot_orbit_deltas_cli
from . import input_handling
from . import output_handling
from . import propagation
from . import tudat_setup


def main() -> None:
    """Main entry point for orbit propagation."""
    # Parse CLI arguments once for script-wide configuration.
    # Only argparse and re have been imported so far, so --help and validation
    # errors are returned instantly without waiting for heavy library loads.
    cli_args = plot_orbit_deltas_cli.parse_arguments()

    # Build propagation inputs from CLI arguments
    propagation_inputs = input_handling.build_propagation_inputs(cli_args)

    # Determine input source for summary
    input_source = "--initial-state" if cli_args.initial_state is not None else "stdin"
    output_oem_path = cli_args.oem
    output_dep_vars_path = cli_args.dep_vars

    # Print pre-propagation summary
    # If writing OEM to stdout, redirect summary to stderr
    if output_oem_path == "-":
        with contextlib.redirect_stdout(sys.stderr):
            output_handling.print_pre_propagation_summary(
                propagation_inputs,
                input_source,
                output_oem_path,
                output_dep_vars_path,
            )
    else:
        output_handling.print_pre_propagation_summary(
            propagation_inputs,
            input_source,
            output_oem_path,
            output_dep_vars_path,
        )

    # Load SPICE kernels
    tudat_setup.load_spice_kernels()

    # Run propagation
    propagation.run_propagation(
        propagation_inputs,
        output_oem_path,
        output_dep_vars_path,
        cli_args.data_only,
    )


if __name__ == "__main__":
    main()
