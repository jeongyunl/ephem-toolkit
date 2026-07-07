#!/usr/bin/env python3
"""Keplerian element propagation.

Read one OEM-like line of Keplerian elements from a file or stdin, then
propagate the orbit using TudatPy's two-body propagator.

Expected input format:
    <ISO-8601 epoch>  <a_km>  <e>  <i_rad>  <omega_rad>  <RAAN_rad>  <theta_rad>

The semi-major axis is interpreted in kilometers and converted to meters before
calling the TudatPy propagator. Output is emitted as the same OEM-like format.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import sys
import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", module="urllib3")
warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.common as common
import common.oem as oem
import common.kepler as kepler

import numpy as np

# CLI defaults
DEFAULT_PROPAGATION_DURATION_S: float = common.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 15.0 * common.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (15 minutes)."""


def import_tudat_modules() -> object:
    """Import TudatPy modules lazily at runtime."""

    from tudatpy.astro import two_body_dynamics

    return two_body_dynamics


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for Keplerian propagation.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``input_file``, ``duration``,
        ``step``, and ``oem``.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Load one OEM-like line of Keplerian elements, propagate using TudatPy, "
            "and write propagated keplerian elements in OEM-like format."
        )
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        metavar="<input_file>",
        help=(
            "Path to a file containing one OEM-like Keplerian element line. "
            "If omitted, read from stdin."
        ),
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=common.parse_duration_to_seconds,
        metavar="<value[s|m|h|d]>",
        default=DEFAULT_PROPAGATION_DURATION_S,
        help=(
            "Propagation duration (default: 1d). "
            "Use -d/--duration, e.g. -d 90, --duration 90s, -d 2m, -d 1.5h, -d 1d."
        ),
    )
    parser.add_argument(
        "-s",
        "--step",
        type=common.parse_step_to_seconds,
        metavar="<value[s|m]>",
        default=DEFAULT_OUTPUT_STEP_S,
        help=(
            "Output interval (default: 15m). "
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


def read_kepler_input(cli_value: str | None) -> tuple[dt.datetime, np.ndarray, str]:
    """Read the initial Keplerian element line from file or stdin.

    Parameters
    ----------
    cli_value : str | None
        Path to an input file, or *None* to read from stdin.

    Returns
    -------
    tuple[dt.datetime, np.ndarray, str]
        ``(epoch_dt, kepler_km, object_name)`` where *kepler_km* is a
        6-element Keplerian state vector in km/rad and *object_name* is
        derived from the file stem or ``"KEPLER_STDIN"``.

    Raises
    ------
    FileNotFoundError
        If *cli_value* is provided but the file does not exist.
    ValueError
        If no valid Keplerian element line is found.
    """
    if cli_value:
        input_path: pathlib.Path = (
            pathlib.Path(cli_value.strip()).expanduser().resolve()
        )
        if not input_path.is_file():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        with input_path.open("r", encoding="utf-8") as handle:
            lines: list[str] = [line.strip() for line in handle if line.strip()]
        parsed: tuple[dt.datetime, np.ndarray] | None = oem.parse_oem_state_line(
            lines[-1]
        )
        if parsed is None:
            raise ValueError(f"No valid Keplerian element line found in {input_path}")
        epoch_dt, kepler_km = parsed
        return epoch_dt, kepler_km, input_path.stem

    if sys.stdin.isatty():
        raise ValueError(
            "Keplerian input not provided. Pass <input_file> or pipe a Keplerian state line on stdin."
        )

    stdin_text: str = sys.stdin.read()
    if not stdin_text.strip():
        raise ValueError(
            "Empty stdin input. Provide a Keplerian element line on stdin."
        )
    lines: list[str] = [
        line.strip() for line in stdin_text.splitlines() if line.strip()
    ]
    parsed: tuple[dt.datetime, np.ndarray] | None = oem.parse_oem_state_line(lines[-1])
    if parsed is None:
        raise ValueError("No valid Keplerian element line found on stdin")
    epoch_dt, kepler_km = parsed
    if epoch_dt.tzinfo is None:
        epoch_dt = epoch_dt.replace(tzinfo=dt.timezone.utc)
    else:
        epoch_dt = epoch_dt.astimezone(dt.timezone.utc)
    return epoch_dt, kepler_km, "KEPLER_STDIN"


def propagate_kepler_elements(
    initial_epoch: dt.datetime,
    initial_kepler_km: np.ndarray,
    duration: float,
    step: float,
    two_body_dynamics_module,
    include_oem_header: bool,
    object_name: str,
) -> None:
    """Propagate the given Keplerian elements and write output lines to stdout.

    Converts the initial Keplerian state from km to m, steps through the
    propagation interval, converts each propagated state back to Cartesian
    km, and writes either a full CCSDS OEM or bare state lines to stdout.

    Parameters
    ----------
    initial_epoch : dt.datetime
        UTC epoch of the initial Keplerian state.
    initial_kepler_km : np.ndarray
        6-element initial Keplerian state vector in km/rad
        ``[a_km, e, i_rad, omega_rad, RAAN_rad, theta_rad]``.
    duration : float
        Propagation duration in seconds.
    step : float
        Output sampling interval in seconds.
    two_body_dynamics_module : module
        TudatPy ``two_body_dynamics`` module used for Keplerian propagation.
    include_oem_header : bool
        If True, write a CCSDS OEM header before the state lines.
    object_name : str
        Object name written to OEM metadata.
    """
    initial_kepler_m: np.ndarray = initial_kepler_km.astype(np.float64).copy()
    initial_kepler_m[kepler.SEMI_MAJOR_AXIS_INDEX] *= 1e3
    initial_kepler_m = initial_kepler_m.reshape((6, 1))

    stop_time: float = duration
    current_time: float = 0.0
    propagated_states: list[tuple[dt.datetime, np.ndarray]] = []
    while current_time <= stop_time + 1.0e-12:
        propagated_kepler: np.ndarray = two_body_dynamics_module.propagate_kepler_orbit(
            initial_kepler_m,
            current_time,
            kepler.MU_EARTH,
        ).flatten()
        propagated_cartesian_m: np.ndarray = kepler.keplerian_to_cartesian(
            propagated_kepler,
            kepler.MU_EARTH,
        ).flatten()
        propagated_cartesian_km: np.ndarray = propagated_cartesian_m * 1e-3
        propagated_states.append(
            (
                initial_epoch + dt.timedelta(seconds=current_time),
                propagated_cartesian_km,
            )
        )
        current_time += step

    if include_oem_header:
        now: str = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[
            :-3
        ]
        stop_epoch: dt.datetime = initial_epoch + dt.timedelta(seconds=duration)

        header: oem.OemHeader = oem.OemHeader(
            version=2.0,
            creation_date=now,
            originator="tudatpy-utils",
        )

        meta: oem.OemMeta = oem.OemMeta(
            object_name=object_name,
            object_id=object_name,
            center_name="EARTH",
            ref_frame="KEPLERIAN",
            time_system="UTC",
            start_time=common.datetime_to_iso8601(initial_epoch),
            stop_time=common.datetime_to_iso8601(stop_epoch),
        )
        oem_message: oem.CcsdsOem = oem.CcsdsOem(
            header=header,
            meta=meta,
            states={state[0].timestamp(): state[1] for state in propagated_states},
        )
        oem_message.to_file(sys.stdout)
    else:
        states_dict: dict[dt.datetime, np.ndarray] = {
            state[0]: state[1] for state in propagated_states
        }
        oem.write_states(sys.stdout, states_dict)


def main() -> int:
    """Execute the Keplerian propagation workflow.

    Returns
    -------
    int
        Process return code. ``0`` on success.
    """
    args: argparse.Namespace = parse_args()
    if args.duration <= 0.0:
        raise ValueError("--duration must be > 0")
    if args.step <= 0.0:
        raise ValueError("--step must be > 0")

    initial_epoch: dt.datetime
    initial_kepler_km: np.ndarray
    object_name: str
    initial_epoch, initial_kepler_km, object_name = read_kepler_input(args.input_file)
    two_body_dynamics_module: object = import_tudat_modules()

    propagate_kepler_elements(
        initial_epoch=initial_epoch,
        initial_kepler_km=initial_kepler_km,
        duration=args.duration,
        step=args.step,
        two_body_dynamics_module=two_body_dynamics_module,
        include_oem_header=args.oem,
        object_name=object_name,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
