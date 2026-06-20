#!/usr/bin/env python3
from __future__ import annotations

"""
# TLE propagation to OEM-like output
## Objectives
Load one TLE file, propagate the orbit with TudatPy's SGP4 TLE ephemeris, and
print state vectors in an OEM-like text format.

The script accepts a TLE file path as a positional CLI argument. When the
positional argument is omitted, TLE text is read directly from stdin.
"""

"""
## Import statements

Only light standard-library modules are imported at file import time. TudatPy
modules are imported only when propagation is actually requested. This keeps
``--help`` and early argument validation responsive.
"""

import argparse
import datetime as dt
import pathlib
import sys
import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", module="urllib3")
warnings.filterwarnings("ignore", category=SyntaxWarning)


import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.common import (
    parse_duration_to_seconds,
    parse_step_to_seconds,
    SECONDS_PER_DAY,
    SECONDS_PER_MINUTE,
)
from common.oem import CcsdsOem, OemHeader, OemMeta

import numpy as np

# CLI defaults
DEFAULT_PROPAGATION_DURATION_S = SECONDS_PER_DAY
DEFAULT_OUTPUT_STEP_S = 15.0 * SECONDS_PER_MINUTE


def import_tudat_modules():
    """Import TudatPy modules lazily at runtime.

    Returns
    -------
    tuple
            ``(data, DateTime, environment_setup, spice)`` modules/classes used by
            the propagation workflow.
    """
    from tudatpy import data
    from tudatpy.astro.time_representation import DateTime
    from tudatpy.dynamics import environment_setup
    from tudatpy.interface import spice

    return data, DateTime, environment_setup, spice


def parse_args() -> argparse.Namespace:
    """Create and parse CLI arguments for TLE propagation.

    Returns
    -------
    argparse.Namespace
            Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Load one TLE file, propagate with TudatPy SGP4, and print an "
            "OEM-like state history."
        )
    )
    parser.add_argument(
        "tle_file",
        nargs="?",
        metavar="<tle_file>",
        help=("Path to a TLE file. If omitted, read TLE text directly from stdin."),
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=parse_duration_to_seconds,
        metavar="<value[s|m|h|d]>",
        default=DEFAULT_PROPAGATION_DURATION_S,
        help=(
            "Propagation duration (default: 1d). "
            "Use -d/--duration, e.g. -d 90, --duration 90s, -d 2m, --duration 1.5h, -d 1d."
        ),
    )
    parser.add_argument(
        "-s",
        "--step",
        type=parse_step_to_seconds,
        metavar="<value[s|m]>",
        default=DEFAULT_OUTPUT_STEP_S,
        help=(
            "Output interval (default: 1m). "
            "Use -s/--step, e.g. -s 60, --step 60s, -s 1m."
        ),
    )
    parser.add_argument(
        "--oem",
        action="store_true",
        help=(
            "Print OEM metadata header before data lines. "
            "If omitted, only propagated state lines are printed."
        ),
    )
    return parser.parse_args()


def extract_tle_line_pair(lines: list[str], source_label: str) -> tuple[str, str]:
    """Extract and validate one TLE line pair from non-empty text lines.

    Parameters
    ----------
    lines : list[str]
            Non-empty candidate lines.
    source_label : str
            Human-readable source used in error messages.

    Returns
    -------
    tuple[str, str]
            Two TLE lines in ``(line1, line2)`` order.

    Raises
    ------
    ValueError
            If fewer than two lines are available or TLE line tags are invalid.
    """
    if len(lines) < 2:
        raise ValueError(
            f"TLE source '{source_label}' must contain at least 2 non-empty lines."
        )

    line1 = lines[-2]
    line2 = lines[-1]
    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError(
            "Could not find TLE line pair at end of input "
            "(expected lines starting with '1 ' and '2 ')."
        )

    return line1, line2


def load_spice_kernels(data_module, spice_module) -> None:
    """Load SPICE kernels required for time conversion.

    Parameters
    ----------
    data_module : module
            TudatPy data module used to resolve kernel directory paths.
    spice_module : module
            TudatPy SPICE interface module used to load kernels.

    Returns
    -------
    None
            This function mutates the global SPICE kernel pool.
    """
    spice_module.load_kernel(
        str(pathlib.Path(data_module.get_spice_kernel_path()) / "naif0012.tls")
    )
    spice_module.load_kernel(
        str(pathlib.Path(data_module.get_spice_kernel_path()) / "pck00011.tpc")
    )


def read_tle_input(cli_value: str | None) -> tuple[str, str, str]:
    """Read TLE lines from file input or stdin text.

    Parameters
    ----------
    cli_value : str | None
            Positional CLI value for TLE file path.

    Returns
    -------
    tuple[str, str, str]
            ``(line1, line2, object_name)`` where ``object_name`` is derived from
            the file stem for file input, or ``TLE_STDIN`` for stdin input.

    Notes
    -----
    For both file and stdin input, the final two non-empty lines are interpreted
    as the TLE pair.
    """
    if cli_value:
        tle_path = pathlib.Path(cli_value.strip()).expanduser().resolve()
        if not tle_path.is_file():
            raise FileNotFoundError(f"TLE file not found: {tle_path}")

        with tle_path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        line1, line2 = extract_tle_line_pair(lines, str(tle_path))
        return line1, line2, tle_path.stem

    if sys.stdin.isatty():
        raise ValueError(
            "TLE input not provided. Pass <tle_file> or pipe TLE text on stdin."
        )

    stdin_text = sys.stdin.read()
    if not stdin_text.strip():
        raise ValueError("Empty stdin input. Provide TLE text on stdin.")
    lines = [line.strip() for line in stdin_text.splitlines() if line.strip()]
    line1, line2 = extract_tle_line_pair(lines, "stdin")
    return line1, line2, "TLE_STDIN"


def epoch_to_utc_iso(epoch_tdb: float, spice_module, datetime_class) -> str:
    """Convert TDB seconds since J2000 to UTC ISO string.

    Parameters
    ----------
    epoch_tdb : float
            TDB epoch in seconds since J2000.
    spice_module : module
            TudatPy SPICE interface module.
    datetime_class : type
            TudatPy DateTime class.

    Returns
    -------
    str
            UTC epoch string in ISO-like form with trailing ``Z``.
    """
    epoch_utc = spice_module.get_approximate_utc_from_tdb(epoch_tdb)
    dt_utc = datetime_class.from_epoch(epoch_utc)
    iso = dt_utc.to_iso_string(number_of_digits_seconds=3)
    if "T" not in iso:
        iso = iso.replace(" ", "T")
    return iso


def print_oem_like(
    object_name: str,
    tle_ephemeris,
    start_tdb: float,
    duration: float,
    step: float,
    spice_module,
    datetime_class,
    include_oem_header: bool,
) -> None:
    """Print propagated state history using an OEM-like text layout.

    Parameters
    ----------
    object_name : str
            Object name/id written to OEM metadata.
    tle_ephemeris : object
            TudatPy ephemeris object exposing ``cartesian_state(epoch)``.
    start_tdb : float
            Start epoch in TDB seconds since J2000.
    duration : float
            Propagation duration in seconds.
    step : float
            Output sampling interval in seconds.
    spice_module : module
            TudatPy SPICE interface module.
    datetime_class : type
            TudatPy DateTime class.
    include_oem_header : bool
            Whether to print OEM metadata header before state lines.

    Returns
    -------
    None
            Writes an OEM-like header and data lines to stdout.
    """
    now = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    stop_tdb = start_tdb + duration
    start_utc_iso = epoch_to_utc_iso(start_tdb, spice_module, datetime_class)
    stop_utc_iso = epoch_to_utc_iso(stop_tdb, spice_module, datetime_class)

    # Propagate and collect state vectors
    states_list = []
    current_tdb = start_tdb
    while current_tdb <= stop_tdb + 1.0e-12:
        state_m = tle_ephemeris.cartesian_state(current_tdb)
        epoch_iso = epoch_to_utc_iso(current_tdb, spice_module, datetime_class)

        # Convert from meters to km
        state_km = np.array(
            [
                state_m[0] / 1000.0,
                state_m[1] / 1000.0,
                state_m[2] / 1000.0,
                state_m[3] / 1000.0,
                state_m[4] / 1000.0,
                state_m[5] / 1000.0,
            ]
        )

        # Parse epoch string and convert to POSIX timestamp (UTC)
        epoch_dt = dt.datetime.fromisoformat(epoch_iso.rstrip("Z"))
        epoch_ts = epoch_dt.replace(tzinfo=dt.timezone.utc).timestamp()
        states_list.append((epoch_ts, state_km))
        current_tdb += step

    if include_oem_header:
        # Create OEM object with metadata
        header = OemHeader(
            version=2.0,
            creation_date=now,
            originator="tudatpy-utils",
        )

        meta = OemMeta(
            object_name=object_name,
            object_id=object_name,
            center_name="EARTH",
            ref_frame="EME2000",
            time_system="UTC",
            start_time=start_utc_iso,
            stop_time=stop_utc_iso,
        )

        oem = CcsdsOem(header=header, meta=meta, states=dict(states_list))
        oem.to_file(sys.stdout)
    else:
        # Print only state lines
        from common.oem import write_states

        states_dict = {epoch: state for epoch, state in states_list}
        write_states(sys.stdout, states_dict)


def main() -> int:
    """Execute the TLE propagation workflow.

    Returns
    -------
    int
            Process return code. ``0`` on success.
    """
    # Parse CLI input and validate scalar settings first so invalid requests
    # fail quickly before importing TudatPy.
    args = parse_args()

    if args.duration <= 0.0:
        raise ValueError("--duration must be > 0")
    if args.step <= 0.0:
        raise ValueError("--step must be > 0")

    line1, line2, object_name = read_tle_input(args.tle_file)

    # Heavy TudatPy imports are intentionally delayed until after cheap input
    # validation is complete.
    data, date_time, environment_setup, spice = import_tudat_modules()
    load_spice_kernels(data, spice)

    tle_ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
    tle_ephemeris = environment_setup.create_body_ephemeris(
        tle_ephemeris_settings, body_name=object_name
    )
    start_tdb = tle_ephemeris.tle.reference_epoch

    print_oem_like(
        object_name=object_name,
        tle_ephemeris=tle_ephemeris,
        start_tdb=start_tdb,
        duration=args.duration,
        step=args.step,
        spice_module=spice,
        datetime_class=date_time,
        include_oem_header=args.oem,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
