#!/usr/bin/env python3
"""OMM propagation to OEM output.

Load one OMM file, determine propagation method based on content:
- If the OMM contains TLE parameters, propagate with TudatPy's SGP4 ephemeris.
- Otherwise, propagate using the two-body Kepler propagator.

Output is emitted as CCSDS OEM state vectors.

Usage:
    propagate-omm <omm_file> [options]
    cat <omm_file> | propagate-omm [options]

Time window options:
    --start <iso8601|duration>   Start epoch (absolute or relative to OMM epoch)
    --stop  <iso8601|duration>   Stop epoch (absolute or relative to start epoch)
"""

from __future__ import annotations

import datetime as dt
import sys
import warnings
from typing import Any

import numpy as np

try:
    from .propagate_omm_cli import PropagateOmmArgs
    from .propagate_omm_cli import parse_arguments
except ImportError:  # pragma: no cover - direct script execution fallback
    from ephem_toolkit.propagate_omm.propagate_omm_cli import PropagateOmmArgs
    from ephem_toolkit.propagate_omm.propagate_omm_cli import parse_arguments

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.kepler as kepler
import ephem_toolkit.core.spice_utils as spice_utils
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.tle as tle_mod

# CLI defaults
DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 5.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (5 minutes)."""


# ===================================================================
# OMM input
# ===================================================================


def read_omm_input(cli_value: str | None) -> omm.CcsdsOmm:
    """Read and parse an OMM from file or stdin.

    Parameters
    ----------
    cli_value : str | None
        Path to OMM file, or "-" for stdin.

    Returns
    -------
    omm.CcsdsOmm
        Parsed OMM object.
    """
    if cli_value == "-" or cli_value is None:
        if sys.stdin.isatty():
            raise ValueError(
                "OMM input not provided. Pass <omm_file> or pipe OMM text on stdin."
            )
        import io

        stdin_text: str = sys.stdin.read()
        if not stdin_text.strip():
            raise ValueError("Empty stdin input. Provide OMM text on stdin.")
        return omm.CcsdsOmm.from_source(io.StringIO(stdin_text))

    return omm.CcsdsOmm.from_source(cli_value)


# ===================================================================
# TLE propagation path (SGP4)
# ===================================================================


def load_spice_kernels() -> None:
    """Load SPICE kernels required for time conversion."""
    spice_kernel_files: list[str] = [
        "naif0012.tls",
        "pck00011.tpc",
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


def propagate_tle_sgp4(
    omm_data: omm.CcsdsOmm,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate OMM with TLE parameters using TudatPy SGP4.

    Parameters
    ----------
    omm_data : omm.CcsdsOmm
        Parsed OMM with TLE parameters.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str
        Output path or "-" for stdout.
    """
    from tudatpy.dynamics import environment_setup

    load_spice_kernels()

    # Convert OMM to TLE, then format TLE lines for SGP4
    tle_obj: tle_mod.Tle = convert_tle.omm_to_tle(omm_data)
    line1, line2 = tle_mod.format_tle_strings(tle_obj)

    object_name: str = omm_data.object_name or "UNKNOWN"

    # Create SGP4 ephemeris
    tle_ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
    tle_ephemeris = environment_setup.create_body_ephemeris(
        tle_ephemeris_settings, body_name=object_name
    )

    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        current_tdb_s: float = time_utils.datetime_to_tdb_s(current_time)
        state_m: np.ndarray = tle_ephemeris.cartesian_state(current_tdb_s)
        timestamp: float = current_time.timestamp()
        propagated_states.append((timestamp, state_m))
        current_time = current_time + step_dt

    _write_oem_output(propagated_states, object_name, data_only, output_path)


# ===================================================================
# Kepler propagation path (two-body)
# ===================================================================


def propagate_kepler_from_omm(
    omm_data: omm.CcsdsOmm,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
    output_path: str = "-",
) -> None:
    """Propagate OMM mean elements using two-body Kepler propagator.

    Parameters
    ----------
    omm_data : omm.CcsdsOmm
        Parsed OMM without TLE parameters.
    start_time : dt.datetime
        Propagation start epoch (UTC).
    stop_time : dt.datetime
        Propagation stop epoch (UTC).
    step_s : float
        Output sampling interval (s).
    data_only : bool
        If True, emit state lines only (no OEM header).
    output_path : str
        Output path or "-" for stdout.
    """
    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    # Convert OMM mean elements to Keplerian state vector [a, e, i, ω, Ω, θ]
    initial_kepler: np.ndarray = np.array(
        [
            kepler.mean_motion_to_semi_major_axis(omm_data.mean_motion),
            omm_data.eccentricity,
            np.radians(omm_data.inclination),
            np.radians(omm_data.arg_of_pericenter),
            np.radians(omm_data.ra_of_asc_node),
            kepler.mean_to_true_anomaly(
                np.radians(omm_data.mean_anomaly), omm_data.eccentricity
            ),
        ],
        dtype=float,
    )

    epoch_dt: dt.datetime = time_utils.iso8601_to_datetime(omm_data.epoch)
    object_name: str = omm_data.object_name or "UNKNOWN"

    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        elapsed_s: float = (current_time - epoch_dt).total_seconds()
        cartesian_m: np.ndarray = kepler.keplerian_to_cartesian(
            kepler.propagate_kepler(initial_kepler, elapsed_s)
        )
        propagated_states.append((current_time.timestamp(), cartesian_m))
        current_time = current_time + step_dt

    _write_oem_output(propagated_states, object_name, data_only, output_path)


# ===================================================================
# Common OEM output
# ===================================================================


def _write_oem_output(
    propagated_states: list[tuple[float, np.ndarray]],
    object_name: str,
    data_only: bool,
    output_path: str,
) -> None:
    """Write propagated states as OEM output.

    Parameters
    ----------
    propagated_states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples.
    object_name : str
        Object name for OEM metadata.
    data_only : bool
        If True, emit state lines only.
    output_path : str
        Output path or "-" for stdout.
    """

    def emit(output_stream: Any) -> None:
        if data_only:
            oem.CcsdsOem.from_states(propagated_states).write_states(output_stream)
        else:
            oem_obj: oem.CcsdsOem = oem.CcsdsOem.from_states(
                propagated_states,
                object_name=object_name,
                ref_frame="EME2000",
                center_name="EARTH",
                time_system="UTC",
            )
            oem_obj.write(output_stream)

    if output_path == "-":
        emit(sys.stdout)
        return

    with open(output_path, "w", encoding="utf-8") as output_stream:
        emit(output_stream)


# ===================================================================
# Time resolution helpers
# ===================================================================


def resolve_epoch_datetime(
    reference_dt: dt.datetime,
    spec: dt.datetime | dt.timedelta,
) -> dt.datetime:
    """Resolve absolute UTC datetime from a datetime or offset specification."""
    if isinstance(spec, dt.timedelta):
        return reference_dt + spec
    return spec


def resolve_time_bounds(
    reference_dt: dt.datetime,
    start_spec: dt.datetime | dt.timedelta,
    stop_spec: dt.datetime | dt.timedelta | None,
    duration_s: float = DEFAULT_PROPAGATION_DURATION_S,
) -> tuple[dt.datetime, dt.datetime]:
    """Resolve absolute start and stop datetimes for a propagation window."""
    start_time = resolve_epoch_datetime(reference_dt, start_spec)
    if stop_spec is None:
        stop_time = start_time + dt.timedelta(seconds=duration_s)
    else:
        stop_time = resolve_epoch_datetime(start_time, stop_spec)
    return start_time, stop_time


# ===================================================================
# Main entry point
# ===================================================================


def main() -> int:
    """Execute the OMM propagation workflow.

    Returns
    -------
    int
        Process return code (0 on success).
    """
    cli_args: PropagateOmmArgs = parse_arguments()

    if cli_args.step <= 0.0:
        raise ValueError("--step must be > 0")

    # Load OMM
    omm_data: omm.CcsdsOmm = read_omm_input(cli_args.omm_file)

    # Determine reference epoch from OMM
    reference_dt: dt.datetime = time_utils.iso8601_to_datetime(omm_data.epoch)

    # Resolve time window
    start_spec: dt.datetime | dt.timedelta
    stop_spec: dt.datetime | dt.timedelta | None

    if cli_args.start is None:
        start_spec = dt.timedelta(0)
    else:
        start_spec = time_utils.parse_time_or_duration(cli_args.start)

    if cli_args.stop is None:
        stop_spec = dt.timedelta(seconds=cli_args.duration_s)
    else:
        stop_spec = time_utils.parse_time_or_duration(cli_args.stop)

    start_time, stop_time = resolve_time_bounds(
        reference_dt, start_spec, stop_spec, cli_args.duration_s
    )

    # Dispatch based on OMM content
    if omm_data.tle_parameters is not None:
        # TLE data present → use SGP4 propagator
        propagate_tle_sgp4(
            omm_data=omm_data,
            start_time=start_time,
            stop_time=stop_time,
            step_s=cli_args.step,
            data_only=cli_args.data_only,
            output_path=cli_args.output_oem,
        )
    else:
        # No TLE data → use two-body Kepler propagator
        propagate_kepler_from_omm(
            omm_data=omm_data,
            start_time=start_time,
            stop_time=stop_time,
            step_s=cli_args.step,
            data_only=cli_args.data_only,
            output_path=cli_args.output_oem,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
