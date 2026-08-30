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
from .propagate_orbit_cli import PropagateOrbitArgs


def main(argv=None) -> None:
    """Main entry point for orbit propagation."""
    cli_args: PropagateOrbitArgs = propagate_orbit_cli.parse_arguments(argv)

    config, initial_state, target_epoch_s = input_handling.build_propagation_inputs(
        cli_args
    )

    input_source = "stdin" if cli_args.input_opm == "-" else cli_args.input_opm
    output_oem_path = cli_args.output_oem
    output_dep_vars_path = cli_args.dep_vars

    if output_oem_path == "-":
        with contextlib.redirect_stdout(sys.stderr):
            output_handling.print_pre_propagation_summary(
                config,
                initial_state,
                target_epoch_s,
                input_source,
                output_oem_path,
                output_dep_vars_path,
            )
    else:
        output_handling.print_pre_propagation_summary(
            config,
            initial_state,
            target_epoch_s,
            input_source,
            output_oem_path,
            output_dep_vars_path,
        )

    from ephem_toolkit.core.propagator.numerical import load_spice_kernels
    load_spice_kernels()

    propagation.run_propagation(
        config,
        initial_state,
        target_epoch_s,
        output_oem_path,
        output_dep_vars_path,
        cli_args.data_only,
    )


if __name__ == "__main__":
    main()
