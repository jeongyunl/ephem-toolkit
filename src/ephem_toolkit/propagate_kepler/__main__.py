#!/usr/bin/env python3
"""Keplerian element propagation.

Read Keplerian elements and metadata from an OPM file or stdin, then propagate
the orbit using the two-body Kepler propagator.

Usage:
    propagate-kepler <input_opm|-> [-d <duration>] [-s <step>] -o <output_oem|->

References:
    https://en.wikipedia.org/wiki/Kepler%27s_equation
    https://en.wikipedia.org/wiki/Orbital_elements

OPM angles are converted from degrees to radians, and the semi-major axis is
converted from kilometers to meters before calling the propagator. OPM metadata
is copied to the generated OEM output.
"""

from __future__ import annotations

import datetime as dt

from . import propagate_kepler_cli

# ===================================================================
# Main entry point
# ===================================================================

from .propagation import propagate_kepler_elements, read_kepler_input


def main(argv=None) -> int:
    """Execute the Keplerian propagation workflow.

    Returns
    -------
    int
        Process return code. ``0`` on success.
    """
    cli_parser = propagate_kepler_cli.build_arg_parser()
    cli_args: propagate_kepler_cli.PropagateKeplerArgs = (
        propagate_kepler_cli.parse_arguments(cli_parser, argv)
    )
    if cli_args.duration_s <= 0.0:
        raise ValueError("--duration must be > 0")
    if cli_args.step_s <= 0.0:
        raise ValueError("--step must be > 0")

    import numpy as np

    initial_epoch: dt.datetime
    initial_kepler_km: np.ndarray
    output_metadata: dict[str, str]
    initial_epoch, initial_kepler_km, output_metadata = read_kepler_input(
        cli_args.input_opm
    )

    propagate_kepler_elements(
        initial_epoch=initial_epoch,
        initial_kepler_km=initial_kepler_km,
        duration_s=cli_args.duration_s,
        step_s=cli_args.step_s,
        data_only=cli_args.data_only,
        output_metadata=output_metadata,
        output_path=cli_args.output_oem,
    )
    return 0


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
