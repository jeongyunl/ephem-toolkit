#!/usr/bin/env python3
"""Perturbed satellite orbit propagation.

Propagates a (quasi-massless) body dominated by a central point-mass attractor,
including multiple perturbing accelerations from the central body and third bodies
(drag, radiation pressure, spherical-harmonic gravity, and point-mass gravity from
Moon, Sun, Mars, and Venus).

The script expects one initial state from a CCSDS OPM input source. Use the
positional argument ``input_opm`` with a file path, or pass ``-`` to read OPM
content from stdin.

Usage:
    propagate-orbit <input_opm|-> [options]
    cat input.opm | propagate-orbit - -o - [options]

References:
    https://public.ccsds.org/Pubs/502x0b3e1.pdf

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


from . import input_handling
from . import output_handling
from . import propagation
from . import propagate_orbit_cli
from . import tudat_setup
from .propagate_orbit_cli import PropagateOrbitArgs


def main() -> None:
    """Main entry point for orbit propagation."""
    # Parse CLI arguments once for script-wide configuration.
    # Only argparse and re have been imported so far, so --help and validation
    # errors are returned instantly without waiting for heavy library loads.
    cli_args: PropagateOrbitArgs = propagate_orbit_cli.parse_arguments()

    # Build propagation inputs from CLI arguments
    propagation_inputs = input_handling.build_propagation_inputs(cli_args)

    # Determine input source for summary
    input_source = "stdin" if cli_args.input_opm == "-" else cli_args.input_opm
    output_oem_path = cli_args.output_oem
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
