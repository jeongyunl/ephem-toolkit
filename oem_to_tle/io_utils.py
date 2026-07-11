"""Input/output and parsing utilities for TLE estimation.

Provides functions to parse OEM (Orbit Ephemeris Message) state vectors,
read input from files or stdin, and parse command-line arguments for
TLE estimation workflows.

References:
    CCSDS Recommended Standard for Orbit Data Messages (OEM).
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys
from datetime import datetime

import numpy as np

Timestamp = float
"""POSIX timestamp (seconds since 1970-01-01 UTC) used as the epoch type throughout the oem_to_tle pipeline."""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.oem as oem


def parse_dataset_from_oem(
    source: str | io.StringIO,
) -> list[tuple[Timestamp, np.ndarray]] | None:
    """Parse a CCSDS OEM source into (timestamp, state_vector_m) records.

    OEM reader now returns state vectors in SI units (m and m/s).

    Parameters
    ----------
    source : str | io.StringIO
        File path (str/Path) or file-like object.

    Returns
    -------
    list[tuple[Timestamp, np.ndarray]] | None
        List of (timestamp, state_vector_m (6,)) tuples, or None if invalid.
        Timestamp is a POSIX float (seconds since 1970-01-01 UTC).
        State vector format: [x, y, z, vx, vy, vz] in meters and m/s.
    """
    try:
        _, _, states = oem.read_oem(source)
    except Exception:
        return None

    if not states:
        return None

    records: list[tuple[Timestamp, np.ndarray]] = []
    for timestamp in sorted(states):
        state_vector_m: np.ndarray = states[timestamp]
        if len(state_vector_m) < 6:
            continue
        # State vectors are already in m and m/s (SI units)
        records.append((float(timestamp), state_vector_m))

    if len(records) < 2:
        return None

    return records


def parse_dataset(input_text: str) -> list[tuple[Timestamp, np.ndarray]]:
    """Parse input text into (timestamp, state_vector) records.

    First attempts to parse as a CCSDS OEM file using common.oem.read_oem.
    Falls back to the legacy line-by-line parser for simple state-vector files.

    OEM parsers now return state vectors in SI units (m and m/s).

    Parameters
    ----------
    input_text : str
        Input text containing state vectors.

    Returns
    -------
    list[tuple[Timestamp, np.ndarray]]
        List of (timestamp, state_vector_m (6,)) tuples.
        Timestamp is a POSIX float (seconds since 1970-01-01 UTC).
        State vector format: [x, y, z, vx, vy, vz] in meters and m/s.

    Raises
    ------
    ValueError
        If fewer than 2 valid state vectors are found.
    """
    # Try CCSDS OEM format first.
    oem_records: list[tuple[Timestamp, np.ndarray]] | None = parse_dataset_from_oem(
        io.StringIO(input_text)
    )
    if oem_records is not None:
        return oem_records

    # Fall back to legacy line-by-line parsing.
    records: list[tuple[Timestamp, np.ndarray]] = []
    for raw_line in input_text.splitlines():
        parsed: tuple[float, np.ndarray] | None = oem.parse_oem_state_line(raw_line)
        if parsed is not None:
            timestamp: float
            state_m: np.ndarray
            timestamp, state_m = parsed
            # State vectors are already in m and m/s (SI units)
            records.append((timestamp, state_m))

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
        with open(input_path, "r", encoding="utf-8") as input_file:
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
