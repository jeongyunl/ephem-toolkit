"""Input handling for orbit propagation.

This module provides functions to read and parse initial state vectors from
various input sources (CLI arguments, stdin) and build consolidated propagation
input structures for orbit simulation.

References:
    https://public.ccsds.org/Pubs/502x0b3e1.pdf
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagatorConfig,
)

from .constants import DEFAULT_SATELLITE_NAME

# ===================================================================
# Input readers
# ===================================================================


def read_initial_state_from_opm_file_or_stdin(
    cli_args: argparse.Namespace,
) -> tuple[np.ndarray, datetime]:
    """Read one initial state record from OPM input sources.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    Source selection is controlled by the positional ``input_opm`` argument:
    1. ``-``: read OPM content from stdin.
    2. any other value: read OPM content from that file path.

    This function prints a user-facing error and exits with status 1 when no
    valid input line is available.

    Returns
    -------
    tuple[numpy.ndarray, datetime]
        ``(initial_state_m_m_s, initial_epoch_datetime_utc)``.
    """
    input_opm = cli_args.input_opm
    if input_opm == "-":
        if sys.stdin.isatty():
            print(
                "Error: positional input_opm '-' requires OPM content from stdin.",
                file=sys.stderr,
            )
            print(
                "Example: cat input.opm | propagate-orbit - -d 86400",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            input_text = sys.stdin.read()
            input_opm_message = opm.CcsdsOpm.from_source(io.StringIO(input_text))
        except Exception as exc:
            print(f"Error: invalid stdin OPM input: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            input_opm_message = opm.CcsdsOpm.from_source(Path(input_opm))
        except Exception as exc:
            print(
                f"Error: failed to read OPM file '{input_opm}': {exc}", file=sys.stderr
            )
            sys.exit(1)

    try:
        initial_epoch_datetime_utc = time_utils.iso8601_to_datetime(
            input_opm_message.state_vector.epoch
        )
    except ValueError as exc:
        print(f"Error: invalid OPM EPOCH value: {exc}", file=sys.stderr)
        sys.exit(1)

    initial_state_m_m_s = (
        input_opm_message.state_vector.values * oem.KILOMETERS_TO_METERS
    )

    return initial_state_m_m_s, initial_epoch_datetime_utc


# ===================================================================
# Propagation input assembly
# ===================================================================


def build_propagation_inputs(
    cli_args: argparse.Namespace,
) -> tuple[NumericalPropagatorConfig, NumericalInitialState, float]:
    """Build propagation inputs from CLI options and parsed state data.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    The OPM input reader returns only the SI state vector and the parsed UTC
    epoch, which are the only values needed downstream.

    Empty or whitespace-only satellite names are normalized to
    ``DEFAULT_SATELLITE_NAME``.

    Returns
    -------
    tuple[NumericalPropagatorConfig, NumericalInitialState, float]
        ``(config, initial_state, target_epoch_s)`` where ``target_epoch_s``
        is the propagation end epoch (TT, s since J2000 TT).
    """
    satellite_name = cli_args.name.strip() if cli_args.name is not None else ""
    if not satellite_name:
        satellite_name = DEFAULT_SATELLITE_NAME

    (
        initial_state_m_m_s,
        initial_epoch_datetime_utc,
    ) = read_initial_state_from_opm_file_or_stdin(cli_args)
    (
        earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order,
    ) = cli_args.earth_gravity

    integrator_step_size_values = tuple(cli_args.integrator_step_size)

    epoch_s: float = time_utils.datetime_to_tt_s(initial_epoch_datetime_utc)
    target_epoch_s: float = epoch_s + cli_args.duration

    config = NumericalPropagatorConfig(
        satellite_name=satellite_name,
        satellite_mass_kg=cli_args.mass,
        integrator_method=cli_args.integrator,
        integrator_step_size_values_s=integrator_step_size_values,
        earth_spherical_harmonic_gravity_degree=earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order=earth_spherical_harmonic_gravity_order,
        satellite_drag_area_m2=cli_args.drag_area,
        is_srp_on=cli_args.srp,
        srp_coefficient=cli_args.srp_coeff,
        is_earth_drag_on=cli_args.drag,
        satellite_drag_coefficient=cli_args.drag_coeff,
        is_moon_gravity_on=cli_args.moon_gravity,
        is_sun_gravity_on=cli_args.sun_gravity,
        is_venus_gravity_on=cli_args.venus_gravity,
        is_mars_gravity_on=cli_args.mars_gravity,
    )
    initial_state = NumericalInitialState(
        state_m_m_s=initial_state_m_m_s,
        epoch_s=epoch_s,
    )
    return config, initial_state, target_epoch_s
