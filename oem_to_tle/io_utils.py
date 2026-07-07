"""Input/output and parsing utilities for TLE estimation."""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timezone

import numpy as np

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.oem as oem


def parse_oem_state_line(line: str) -> tuple[datetime, np.ndarray, np.ndarray] | None:
    """Parse one OEM-like Cartesian state line.

    Expected format:
    UTC_ISO x_km y_km z_km vx_km_s vy_km_s vz_km_s

    Fields may be separated by whitespace or commas. A trailing "Z" suffix on
    the epoch is accepted and stripped before ISO parsing.

    Parameters
    ----------
    line : str
        Input line to parse.

    Returns
    -------
    tuple[datetime, np.ndarray, np.ndarray] | None
        Tuple of (epoch, position_km (3,), velocity_km_s (3,)) or None if line is empty/comment.

    Raises
    ------
    ValueError
        If line format is invalid or contains non-numeric state fields.
    """
    stripped: str = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    parts: list[str] = [p for token in stripped.split() for p in token.split(",")]
    if len(parts) < 7:
        raise ValueError(f"Line does not contain 7 fields: '{line.rstrip()}'")

    epoch_text: str = parts[0]
    if epoch_text.endswith("Z"):
        epoch_text = epoch_text[:-1]

    try:
        epoch_dt: datetime = datetime.fromisoformat(epoch_text)
    except ValueError as error:
        raise ValueError(
            f"Invalid epoch '{parts[0]}': expected ISO format like 2026-05-31T12:34:56.000"
        ) from error

    try:
        x, y, z, vx, vy, vz = (float(value) for value in parts[1:7])
    except ValueError as error:
        raise ValueError(
            f"Invalid numeric state fields in line: '{line.rstrip()}'"
        ) from error

    return epoch_dt, np.array([x, y, z]), np.array([vx, vy, vz])  # (3,), (3,)


def parse_dataset_from_oem(
    source: str | io.StringIO,
) -> list[tuple[datetime, np.ndarray, np.ndarray]] | None:
    """Parse a CCSDS OEM source into (epoch, position_km, velocity_km_s) records.

    Parameters
    ----------
    source : str | io.StringIO
        File path (str/Path) or file-like object.

    Returns
    -------
    list[tuple[datetime, np.ndarray, np.ndarray]] | None
        List of (epoch, position_km (3,), velocity_km_s (3,)) tuples, or None if invalid.
    """
    try:
        _, _, states = oem.read_oem(source)
    except Exception:
        return None

    if not states:
        return None

    records: list[tuple[datetime, np.ndarray, np.ndarray]] = []
    for timestamp in sorted(states):
        sv = states[timestamp]
        if len(sv) < 6:
            continue
        # Convert timestamp back to datetime object
        epoch: datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        position_km: np.ndarray = np.array(
            [float(sv[0]), float(sv[1]), float(sv[2])]
        )  # (3,)
        velocity_km_s: np.ndarray = np.array(
            [float(sv[3]), float(sv[4]), float(sv[5])]
        )  # (3,)
        records.append((epoch, position_km, velocity_km_s))

    if len(records) < 2:
        return None

    return records


def parse_dataset(input_text: str) -> list[tuple[datetime, np.ndarray, np.ndarray]]:
    """Parse input text into (epoch, position, velocity) records.

    First attempts to parse as a CCSDS OEM file using common.oem.read_oem.
    Falls back to the legacy line-by-line parser for simple state-vector files.

    Parameters
    ----------
    input_text : str
        Input text containing state vectors.

    Returns
    -------
    list[tuple[datetime, np.ndarray, np.ndarray]]
        List of (epoch, position_km (3,), velocity_km_s (3,)) tuples.

    Raises
    ------
    ValueError
        If fewer than 2 valid state vectors are found.
    """
    # Try CCSDS OEM format first.
    oem_records: list[tuple[datetime, np.ndarray, np.ndarray]] | None = (
        parse_dataset_from_oem(io.StringIO(input_text))
    )
    if oem_records is not None:
        return oem_records

    # Fall back to legacy line-by-line parsing.
    records: list[tuple[datetime, np.ndarray, np.ndarray]] = []
    for raw_line in input_text.splitlines():
        parsed: tuple[datetime, np.ndarray, np.ndarray] | None = parse_oem_state_line(
            raw_line
        )
        if parsed is not None:
            records.append(parsed)

    if len(records) < 2:
        raise ValueError("Need at least 2 OEM-like state vectors to estimate TLE trend")

    return records


def read_input_text(input_path: str) -> str:
    """Read input text from file or stdin.

    Parameters
    ----------
    input_path : str
        Input file path or '-' for stdin.

    Returns
    -------
    str
        Input text content.

    Raises
    ------
    ValueError
        If input is empty or file cannot be read.
    """
    if input_path == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise ValueError("No input from stdin")
        return text

    try:
        with open(input_path, "r") as input_file:
            text = input_file.read()
    except OSError as error:
        raise ValueError(
            f"Could not read input file '{input_path}': {error}"
        ) from error

    if not text.strip():
        raise ValueError(f"Input file '{input_path}' is empty")

    return text


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Read a set of OEM-like state vectors, estimate TLE element values, "
            "and write the resulting TLE to a file or stdout."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.dat>",
        help=(
            "Input OEM-like state-vector file path. Use '-' or omit to read from stdin "
            "(default: '-')."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help=(
            "Output TLE file path (default: '-'). "
            "Use '-' to print TLE text to stdout."
        ),
    )
    parser.add_argument(
        "--name",
        metavar="<name>",
        default="",
        help="Optional satellite name written above line 1.",
    )
    parser.add_argument(
        "--satellite-number",
        type=int,
        default=99999,
        metavar="<0..99999>",
        help="NORAD satellite number for the generated command (default: 99999).",
    )
    parser.add_argument(
        "--classification",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        help="Classification code for the generated command (default: U).",
    )
    parser.add_argument(
        "--int-designator-year",
        type=int,
        default=0,
        metavar="<0..99>",
        help="International designator launch year (default: 0).",
    )
    parser.add_argument(
        "--int-designator-launch-number",
        type=int,
        default=0,
        metavar="<0..999>",
        help="International designator launch number (default: 0).",
    )
    parser.add_argument(
        "--int-designator-piece",
        default="A",
        metavar="<piece>",
        help="International designator piece identifier (default: A).",
    )
    parser.add_argument(
        "--ephemeris-type",
        type=int,
        default=0,
        metavar="<0..9>",
        help="Ephemeris type value for generated command (default: 0).",
    )
    parser.add_argument(
        "--element-set-number",
        type=int,
        default=1,
        metavar="<0..9999>",
        help="Element set number for generated command (default: 1).",
    )
    parser.add_argument(
        "--bstar",
        default="00000+0",
        metavar="<tle-exp>",
        help="BSTAR drag term for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--mean-motion-second-derivative",
        default="00000+0",
        metavar="<tle-exp>",
        help="Second derivative of mean motion for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--revolution-number-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        help="Revolution number at epoch for generated command (default: 0).",
    )
    parser.add_argument(
        "--refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        help=(
            "Refinement method for matching TLE elements to the epoch state. "
            "'cartesian' (default): minimize SGP4 Cartesian state residual "
            "(requires tudatpy). "
            "'keplerian': minimize osculating Keplerian element residual via "
            "common.convert_tle.tle_to_osculating_keplerian (no SGP4 needed). "
            "'none': skip refinement entirely."
        ),
    )
    return parser.parse_args()
