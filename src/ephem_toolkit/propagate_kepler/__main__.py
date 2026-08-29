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
import io
import pathlib
import sys
import warnings
from typing import TextIO

import numpy as np

from . import propagate_kepler_cli

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.propagator.kepler as kepler
from ephem_toolkit.core.propagator import KeplerPropagator, KeplerianState, OutputMode
import ephem_toolkit.core.time_utils as time_utils

# ===================================================================
# Constants
# ===================================================================

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 15.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (15 minutes)."""


# ===================================================================
# Command-line interface
# ===================================================================


def parse_arguments(argv=None) -> propagate_kepler_cli.PropagateKeplerArgs:
    """Parse command-line arguments for Keplerian propagation.

    Delegates to the canonical propagation-family parser so the console entry
    point and the dedicated parser module stay in sync.
    """
    return propagate_kepler_cli.parse_arguments(argv)


def read_kepler_input(
    source: str | None,
) -> tuple[dt.datetime, np.ndarray, dict[str, str]]:
    """Read Keplerian elements and metadata from an OPM file or stdin."""
    if source is None:
        source = "-"

    if source == "-":
        if sys.stdin.isatty():
            raise ValueError(
                "OPM input not provided. Pass <input_opm> or pipe OPM content on stdin."
            )

        stdin_text: str = sys.stdin.read()
        if not stdin_text.strip():
            raise ValueError("Empty stdin input. Provide OPM content on stdin.")
        opm_message = opm.CcsdsOpm.from_source(io.StringIO(stdin_text))
    else:
        input_path: pathlib.Path = pathlib.Path(source).expanduser().resolve()
        opm_message = opm.CcsdsOpm.from_source(input_path)

    elements = opm_message.keplerian_elements
    if elements is None:
        raise ValueError("OPM input does not contain Keplerian elements")
    if elements.true_anomaly is not None:
        true_anomaly_deg = elements.true_anomaly
    elif elements.mean_anomaly is not None:
        true_anomaly_deg = np.degrees(
            kepler.mean_to_true_anomaly(
                np.radians(elements.mean_anomaly), elements.eccentricity
            )
        )
    else:  # pragma: no cover - OPM validation rejects this case
        raise ValueError("OPM input does not contain an anomaly")

    epoch_dt = time_utils.iso8601_to_datetime(opm_message.state_vector.epoch)
    kepler_km = np.array(
        [
            elements.semi_major_axis,
            elements.eccentricity,
            np.radians(elements.inclination),
            np.radians(elements.arg_of_pericenter),
            np.radians(elements.ra_of_asc_node),
            np.radians(true_anomaly_deg),
        ],
        dtype=float,
    )
    output_metadata = {
        output_key: str(opm_message.metadata[opm_key])
        for output_key, opm_key in (
            ("object_name", "OBJECT_NAME"),
            ("ref_frame", "REF_FRAME"),
            ("center_name", "CENTER_NAME"),
            ("time_system", "TIME_SYSTEM"),
        )
    }
    return epoch_dt, kepler_km, output_metadata


# ===================================================================
# Propagation
# ===================================================================


def propagate_kepler_elements(
    initial_epoch: dt.datetime,
    initial_kepler_km: np.ndarray,
    duration_s: float,
    step_s: float,
    data_only: bool,
    output_metadata: dict[str, str],
    output_path: str = "-",
) -> None:
    """Propagate Keplerian elements and write output lines to a stream.

    Converts the initial Keplerian state from km to m, steps through the
    propagation interval, and writes Cartesian states in the internal SI
    units expected by the OEM writer. Output is either a full CCSDS OEM or
    bare state lines to stdout or a file path provided via ``output_path``.
    Full OEM output uses metadata from the input OPM.
    """
    initial_kepler_m: np.ndarray = initial_kepler_km.astype(np.float64).copy()
    initial_kepler_m[kepler.SEMI_MAJOR_AXIS_INDEX] *= 1000.0  # Convert km to m

    # Create propagator once outside loop
    initial_epoch_tt_s = time_utils.datetime_to_tt_s(initial_epoch)
    kepler_state = KeplerianState(elements=initial_kepler_m, epoch_s=initial_epoch_tt_s)
    propagator = KeplerPropagator(initial_state=kepler_state)

    stop_time_s: float = duration_s
    current_time_s: float = 0.0
    # Build list of (TT seconds since J2000, state vector) tuples
    propagated_states: list[tuple[float, np.ndarray]] = []
    while current_time_s <= stop_time_s + 1.0e-12:
        target_epoch_tt_s = initial_epoch_tt_s + current_time_s
        epoch_tt_s, propagated_cartesian_m = propagator.propagate_to(
            target_epoch_tt_s, output=OutputMode.FINAL
        )
        propagated_states.append((epoch_tt_s, propagated_cartesian_m))
        current_time_s += step_s

    output_stream: TextIO
    if output_path == "-":
        output_stream = sys.stdout
    else:
        output_stream = open(output_path, "w", encoding="utf-8")

    try:
        if not data_only:
            # Use from_states() for automatic header/metadata generation.
            # The OEM writer converts these internal SI states to CCSDS km.
            oem_message: oem.CcsdsOem = oem.CcsdsOem.from_states(
                propagated_states,
                **output_metadata,
            )
            oem_message.write(output_stream)
        else:
            oem.CcsdsOem.from_states(propagated_states).write_states(output_stream)
    finally:
        if output_path != "-":
            output_stream.close()


# ===================================================================
# Main entry point
# ===================================================================


def main(argv=None) -> int:
    """Execute the Keplerian propagation workflow.

    Returns
    -------
    int
        Process return code. ``0`` on success.
    """
    cli_args: propagate_kepler_cli.PropagateKeplerArgs = parse_arguments(argv)
    if cli_args.duration_s <= 0.0:
        raise ValueError("--duration must be > 0")
    if cli_args.step_s <= 0.0:
        raise ValueError("--step must be > 0")

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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
