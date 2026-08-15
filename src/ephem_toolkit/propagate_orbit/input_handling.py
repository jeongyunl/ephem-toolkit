"""Input handling for orbit propagation.

This module provides functions to read and parse initial state vectors from
various input sources (CLI arguments, stdin) and build consolidated propagation
input structures for orbit simulation.
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timezone

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem

from .constants import DEFAULT_SATELLITE_NAME
from .data_structures import PropagationInputs


def read_initial_state_from_stream(
    stream: io.TextIOBase,
) -> tuple[np.ndarray, datetime]:
    """Read one OEM-like state record from a text stream.

    Parameters
    ----------
    stream : io.TextIOBase
        Input stream providing one state line.

    Expected line format is:
    ``YYYY-MM-DDTHH:MM:SS.sss x y z vx vy vz`` where position is in km and
    velocity is in km/s.

    Returns
    -------
    tuple[numpy.ndarray, datetime]
        ``(initial_state_m_m_s, initial_epoch_datetime_utc)`` where
        ``initial_state_m_m_s`` is a 6-element cartesian state in SI units (m, m/s).
    """
    line: str = stream.readline()
    if line == "":
        raise ValueError("No input line available in stream")

    parsed_state: tuple[float, np.ndarray] | None = oem.CcsdsOem.parse_oem_state_line(
        line
    )
    if parsed_state is None:
        raise ValueError("The first input line is blank/comment and was not parsed")

    timestamp: float
    state_m_m_s: np.ndarray
    timestamp, state_m_m_s = parsed_state
    initial_epoch_datetime_utc: datetime = datetime.fromtimestamp(
        timestamp, tz=timezone.utc
    )
    # parse_oem_state_line now returns meters (SI units), no conversion needed
    return state_m_m_s, initial_epoch_datetime_utc


def read_initial_state_from_cli_or_stdin(
    cli_args: argparse.Namespace,
) -> tuple[np.ndarray, datetime]:
    """Read one OEM-like state record from CLI input sources.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    Source precedence is:
    1. ``--initial-state`` value, if provided.
    2. One line from stdin, when stdin is piped.

    This function prints a user-facing error and exits with status 1 when no
    valid input line is available.

    Returns
    -------
    tuple[numpy.ndarray, datetime]
        ``(initial_state_m_m_s, initial_epoch_datetime_utc)``.
    """
    if cli_args.initial_state is not None:
        try:
            return read_initial_state_from_stream(
                io.StringIO(cli_args.initial_state + "\n")
            )
        except ValueError as exc:
            print(f"Error: invalid --initial-state value: {exc}", file=sys.stderr)
            sys.exit(1)

    if not sys.stdin.isatty():
        try:
            return read_initial_state_from_stream(sys.stdin)
        except ValueError as exc:
            print(f"Error: invalid stdin input: {exc}", file=sys.stderr)
            sys.exit(1)

    print(
        "Error: missing input data. Provide one OEM-style state line via --initial-state or stdin.",
        file=sys.stderr,
    )
    print(
        "Example (CLI): .../perturbed_satellite_orbit.py --duration 86400 --initial-state '2023-04-10T00:00:00.000 7000 0 0 0 7.5 1.0'",
        file=sys.stderr,
    )
    print(
        "Example (stdin): echo '2023-04-10T00:00:00.000 7000 0 0 0 7.5 1.0' | .../perturbed_satellite_orbit.py -d 86400",
        file=sys.stderr,
    )
    sys.exit(1)


def build_propagation_inputs(cli_args: argparse.Namespace) -> PropagationInputs:
    """Build propagation inputs from CLI options and parsed state data.

    Parameters
    ----------
    cli_args : argparse.Namespace
        Parsed CLI arguments.

    The initial-state reader returns only the SI state vector and the parsed UTC
    epoch, which are the only values needed downstream.

    Empty or whitespace-only satellite names are normalized to
    ``DEFAULT_SATELLITE_NAME``.

    Returns
    -------
    PropagationInputs
        Consolidated, validated propagation inputs.
    """
    satellite_name = cli_args.name.strip() if cli_args.name is not None else ""
    if not satellite_name:
        satellite_name = DEFAULT_SATELLITE_NAME

    (
        initial_state_m_m_s,
        initial_epoch_datetime_utc,
    ) = read_initial_state_from_cli_or_stdin(cli_args)
    (
        earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order,
    ) = cli_args.earth_gravity

    integrator_step_size_values = tuple(cli_args.integrator_step_size)

    return PropagationInputs(
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
        initial_epoch_datetime_utc=initial_epoch_datetime_utc,
        initial_state_m_m_s=initial_state_m_m_s,
        simulation_duration_s=cli_args.duration,
    )
