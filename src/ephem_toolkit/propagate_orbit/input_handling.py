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
from datetime import datetime
from pathlib import Path

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagatorConfig,
)

from .constants import (
    DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
    DEFAULT_SATELLITE_DRAG_COEFFICIENT,
    DEFAULT_SATELLITE_MASS_KG,
    DEFAULT_SATELLITE_NAME,
    DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
)

# ===================================================================
# Input readers
# ===================================================================


def read_initial_state_from_opm_file_or_stdin(
    cli_args: argparse.Namespace,
) -> tuple[
    np.ndarray,
    datetime,
    str,
    str,
    tuple[str, ...],
    opm.OpmSpacecraftParameters | None,
]:
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
    tuple[numpy.ndarray, datetime, str, str, tuple[str, ...], OpmSpacecraftParameters | None]
        State, UTC epoch, object ID, object name, source header comments, and
        optional OPM spacecraft parameters.
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

    required_context = {
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "J2000",
        "TIME_SYSTEM": "UTC",
    }
    for field_name, expected_value in required_context.items():
        actual_value = str(input_opm_message.metadata.get(field_name, "")).strip()
        if actual_value.upper() != expected_value:
            print(
                f"Error: propagate-orbit requires {field_name}={expected_value}; "
                f"OPM input has {field_name}={actual_value or '<missing>'}.",
                file=sys.stderr,
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

    object_id = str(input_opm_message.metadata.get("OBJECT_ID", ""))
    object_name = str(input_opm_message.metadata.get("OBJECT_NAME", ""))
    source_comments = tuple(input_opm_message.header.comments)
    return (
        initial_state_m_m_s,
        initial_epoch_datetime_utc,
        object_id,
        object_name,
        source_comments,
        input_opm_message.spacecraft_parameters,
    )


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

    The OPM input reader returns the SI state vector, parsed UTC epoch, object
    identifier, and source object name for generated OEM metadata.

    An explicit CLI name takes precedence over the source OPM name; otherwise
    the source name is used, falling back to ``DEFAULT_SATELLITE_NAME``.

    Returns
    -------
    tuple[NumericalPropagatorConfig, NumericalInitialState, float]
        ``(config, initial_state, target_epoch_s)`` where ``target_epoch_s``
        is the propagation end epoch (TT, s since J2000 TT).
    """
    (
        initial_state_m_m_s,
        initial_epoch_datetime_utc,
        object_id,
        source_object_name,
        source_comments,
        opm_spacecraft_parameters,
    ) = read_initial_state_from_opm_file_or_stdin(cli_args)
    satellite_name = (
        cli_args.name.strip()
        if cli_args.name and cli_args.name.strip()
        else source_object_name.strip() or DEFAULT_SATELLITE_NAME
    )
    (
        earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order,
    ) = cli_args.earth_gravity

    integrator_step_size_values = tuple(cli_args.integrator_step_size)

    opm_parameters = opm_spacecraft_parameters
    mass = cli_args.mass
    if mass is None:
        mass = (
            opm_parameters.mass
            if opm_parameters is not None and opm_parameters.mass is not None
            else DEFAULT_SATELLITE_MASS_KG
        )
    drag_area = cli_args.drag_area
    if drag_area is None:
        drag_area = (
            opm_parameters.drag_area
            if opm_parameters is not None and opm_parameters.drag_area is not None
            else DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2
        )
    srp_area = drag_area
    if cli_args.drag_area is None and opm_parameters is not None:
        if opm_parameters.solar_rad_area is not None:
            srp_area = opm_parameters.solar_rad_area
    drag_coefficient = cli_args.drag_coeff
    if drag_coefficient is None:
        drag_coefficient = (
            opm_parameters.drag_coeff
            if opm_parameters is not None and opm_parameters.drag_coeff is not None
            else DEFAULT_SATELLITE_DRAG_COEFFICIENT
        )
    srp_coefficient = cli_args.srp_coeff
    if srp_coefficient is None:
        srp_coefficient = (
            opm_parameters.solar_rad_coeff
            if opm_parameters is not None and opm_parameters.solar_rad_coeff is not None
            else DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT
        )

    epoch_s: float = time_utils.datetime_to_tt_s(initial_epoch_datetime_utc)
    target_epoch_s: float = epoch_s + cli_args.duration

    config = NumericalPropagatorConfig(
        satellite_name=satellite_name,
        satellite_mass_kg=mass,
        integrator_method=cli_args.integrator,
        integrator_step_size_values_s=integrator_step_size_values,
        earth_spherical_harmonic_gravity_degree=earth_spherical_harmonic_gravity_degree,
        earth_spherical_harmonic_gravity_order=earth_spherical_harmonic_gravity_order,
        satellite_drag_area_m2=drag_area,
        satellite_srp_area_m2=srp_area,
        is_srp_on=cli_args.srp,
        srp_coefficient=srp_coefficient,
        is_earth_drag_on=cli_args.drag,
        satellite_drag_coefficient=drag_coefficient,
        is_moon_gravity_on=cli_args.moon_gravity,
        is_sun_gravity_on=cli_args.sun_gravity,
        is_venus_gravity_on=cli_args.venus_gravity,
        is_mars_gravity_on=cli_args.mars_gravity,
        object_id=object_id,
        source_comments=source_comments,
    )
    initial_state = NumericalInitialState(
        state_m_m_s=initial_state_m_m_s,
        epoch_s=epoch_s,
    )
    return config, initial_state, target_epoch_s
