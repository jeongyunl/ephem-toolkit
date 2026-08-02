#!/usr/bin/env python3
"""Compare corresponding states from two OEM files.

Usage:
    python3 bin/diff_oem.py <reference_oem.oem> <comparison_oem.oem>
    python3 bin/diff_oem.py - <comparison_oem.oem>
    python3 bin/diff_oem.py <reference_oem.oem> -

The utility reports time, position, and velocity differences. Use ``-`` for one
stdin input. Interpolation options compare states at matching epochs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.interpolator.lagrange as lagrange
import common.common as common
import common.oem as oem
import common.time_utils as time_utils

INTERPOLATION_DEGREE: int = 8
"""Polynomial degree used for OEM state interpolation."""


@dataclass
class ComparisonResult:
    """Named results returned by :func:`compare_states`."""

    reference_epoch: datetime
    """Reference state epoch."""

    comparison_epoch: datetime
    """Comparison state epoch."""

    time_diff_s: float | None
    """Comparison epoch minus reference epoch, when no interpolation is used."""

    position_diff_km: np.ndarray
    """Comparison minus reference position (km)."""

    position_diff_magnitude_km: float
    """Magnitude of the position difference (km)."""

    velocity_diff_km_s: np.ndarray
    """Comparison minus reference velocity (km/s)."""

    velocity_diff_magnitude_km_s: float
    """Magnitude of the velocity difference (km/s)."""

    rtn_position_km: np.ndarray
    """Comparison minus reference position in the reference RTN frame (km)."""

    rtn_velocity_km_s: np.ndarray
    """Comparison minus reference velocity in the reference RTN frame (km/s)."""


def read_states(source: TextIO | str | Path) -> list[tuple[float, np.ndarray]]:
    """Read all states from an OEM file or text stream.

    Comments and blank lines are skipped by :class:`oem.CcsdsOem`.

    Parameters
    ----------
    source : TextIO, str, or pathlib.Path
        Readable OEM stream or path to an OEM file containing state data.

    Returns
    -------
    list[tuple[float, np.ndarray]]
        ``(timestamp, state_m)`` pairs where *timestamp* is POSIX seconds and
        *state_m* is a six-element vector in meters and meters per second.

    Raises
    ------
    ValueError
        If file cannot be read or no valid state is found.
    """
    try:
        oem_data = oem.CcsdsOem.read(source)
    except OSError as error:
        raise ValueError(f"Could not read file '{source}': {error}") from error

    if not oem_data.states:
        raise ValueError(f"No valid OEM-like state found in '{source}'")
    return oem_data.states


def _get_overlapping_time_range(
    reference_states: list[tuple[float, np.ndarray]],
    comparison_states: list[tuple[float, np.ndarray]],
) -> tuple[float, float] | None:
    """Return the inclusive time range shared by two ordered state lists."""
    overlap_start: float = max(reference_states[0][0], comparison_states[0][0])
    overlap_stop: float = min(reference_states[-1][0], comparison_states[-1][0])
    if overlap_start > overlap_stop:
        return None
    return overlap_start, overlap_stop


def _resolve_time_bound(value: str, reference_epoch_s: float) -> float:
    """Resolve an absolute or reference-relative time bound to POSIX seconds."""
    parsed_value: datetime | timedelta = time_utils.parse_time_or_duration(value)
    reference_datetime: datetime = datetime.fromtimestamp(
        reference_epoch_s, tz=timezone.utc
    )
    if isinstance(parsed_value, timedelta):
        parsed_value = reference_datetime + parsed_value
    return parsed_value.timestamp()


def compare_states(
    reference_oem: tuple[float, np.ndarray],
    comparison_oem: tuple[float, np.ndarray],
    reference_interpolator: lagrange.LagrangeInterpolator | None = None,
    comparison_interpolator: lagrange.LagrangeInterpolator | None = None,
) -> ComparisonResult:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    reference_oem : tuple[float, np.ndarray]
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : tuple[float, np.ndarray]
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : LagrangeInterpolator, optional
        Interpolator built from the reference OEM. When provided, the reference
        state is evaluated at the comparison epoch instead of using the supplied
        reference state's epoch and vector.
    comparison_interpolator : LagrangeInterpolator, optional
        Interpolator built from the comparison OEM. When provided, the comparison
        state is evaluated at the reference epoch.

    Returns
    -------
    ComparisonResult
        Comparison result containing epochs, time difference in seconds,
        position difference in km, and velocity difference in km/s.
    """
    reference_timestamp: float
    reference_state_m: np.ndarray
    reference_timestamp, reference_state_m = reference_oem
    comparison_timestamp: float
    comparison_state_m: np.ndarray
    comparison_timestamp, comparison_state_m = comparison_oem
    if comparison_interpolator is not None:
        comparison_timestamp = reference_timestamp
        interpolated_state: np.ndarray | None = comparison_interpolator.interpolate(
            reference_timestamp
        )
        if interpolated_state is None:
            reference_epoch = datetime.fromtimestamp(
                reference_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Reference epoch "
                f"{time_utils.datetime_to_iso8601(reference_epoch)} is outside "
                "the comparison OEM interpolation range"
            )
        comparison_state_m = interpolated_state

    if reference_interpolator is not None:
        interpolation_timestamp = comparison_timestamp
        interpolated_state = reference_interpolator.interpolate(interpolation_timestamp)
        if interpolated_state is None:
            comparison_epoch = datetime.fromtimestamp(
                interpolation_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Comparison epoch "
                f"{time_utils.datetime_to_iso8601(comparison_epoch)} is outside "
                "the reference OEM interpolation range"
            )
        reference_timestamp = interpolation_timestamp
        reference_state_m = interpolated_state

    reference_epoch = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    comparison_epoch = datetime.fromtimestamp(comparison_timestamp, tz=timezone.utc)
    reference_position_km: np.ndarray = (
        reference_state_m[0:3] / oem.KILOMETERS_TO_METERS
    )
    reference_velocity_km_s: np.ndarray = (
        reference_state_m[3:6] / oem.KILOMETERS_TO_METERS
    )
    comparison_position_km: np.ndarray = (
        comparison_state_m[0:3] / oem.KILOMETERS_TO_METERS
    )
    comparison_velocity_km_s: np.ndarray = (
        comparison_state_m[3:6] / oem.KILOMETERS_TO_METERS
    )

    time_diff_s: float | None = None
    if reference_interpolator is None and comparison_interpolator is None:
        time_diff_s = (comparison_epoch - reference_epoch).total_seconds()

    position_diff_km: np.ndarray = comparison_position_km - reference_position_km
    position_diff_magnitude_km: float = float(np.linalg.norm(position_diff_km))

    velocity_diff_km_s: np.ndarray = comparison_velocity_km_s - reference_velocity_km_s
    velocity_diff_magnitude_km_s: float = float(np.linalg.norm(velocity_diff_km_s))
    rtn_state_m_s: np.ndarray = common.transform_to_rtn(
        comparison_state_m, reference_state_m
    )
    rtn_position_km: np.ndarray = rtn_state_m_s[0:3] / oem.KILOMETERS_TO_METERS
    rtn_velocity_km_s: np.ndarray = rtn_state_m_s[3:6] / oem.KILOMETERS_TO_METERS

    return ComparisonResult(
        reference_epoch=reference_epoch,
        comparison_epoch=comparison_epoch,
        time_diff_s=time_diff_s,
        position_diff_km=position_diff_km,
        position_diff_magnitude_km=position_diff_magnitude_km,
        velocity_diff_km_s=velocity_diff_km_s,
        velocity_diff_magnitude_km_s=velocity_diff_magnitude_km_s,
        rtn_position_km=rtn_position_km,
        rtn_velocity_km_s=rtn_velocity_km_s,
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``reference_oem``,
        ``comparison_oem``, ``verbose``, ``interpolate_ref``, and
        ``interpolate_data``. The ``--interpolate`` convenience option enables
        both interpolation flags, and is represented by the parsed interpolation
        attributes.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare two OEM-like Cartesian states and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "reference_oem",
        metavar="<reference_oem.oem>",
        help="Reference OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "comparison_oem",
        metavar="<comparison_oem.oem>",
        help="Comparison OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    parser.add_argument(
        "--interpolate-ref",
        action="store_true",
        help="Interpolate the reference OEM at each comparison state timestamp.",
    )
    parser.add_argument(
        "--interpolate-data",
        action="store_true",
        help="Interpolate comparison data at each reference state timestamp.",
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        help="Interpolate both reference and comparison OEM data.",
    )
    parser.add_argument(
        "--rtn",
        action="store_true",
        help="Include comparison state coordinates in the reference RTN frame.",
    )
    parser.add_argument(
        "--start",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Start epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
    )
    parser.add_argument(
        "--stop",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Stop epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
    )
    args = parser.parse_args()
    if args.interpolate:
        args.interpolate_ref = True
        args.interpolate_data = True
    if args.reference_oem == "-" and args.comparison_oem == "-":
        parser.error("reference_oem and comparison_oem cannot both be '-'")
    return args


def _get_output_columns(
    include_time_difference: bool,
    verbose: bool,
    rtn: bool,
    include_comparison_epoch: bool,
) -> list[str]:
    """Return output column names for the selected comparison details."""
    columns: list[str] = ["index", "reference\nepoch"]
    if include_comparison_epoch:
        columns.append("comparison\nepoch")
    if include_time_difference:
        columns.append("time\ndifference\n(s)")
    columns.extend(["position\ndifference\n(km)", "velocity\ndifference\n(km/s)"])
    if verbose:
        columns.extend(
            [
                "dX\n(km)",
                "dY\n(km)",
                "dZ\n(km)",
                "dVX\n(km/s)",
                "dVY\n(km/s)",
                "dVZ\n(km/s)",
            ]
        )
    if rtn:
        columns.extend(
            [
                "RTN r\n(km)",
                "RTN t\n(km)",
                "RTN n\n(km)",
                "RTN vr\n(km/s)",
                "RTN vt\n(km/s)",
                "RTN vn\n(km/s)",
            ]
        )
    return columns


def _format_output_row(values: list[str], columns: list[str]) -> str:
    """Format output values in consistently spaced columns."""
    column_widths = _get_output_column_widths(columns)
    aligned_values = [
        f"{value:>{width}}" for value, width in zip(values, column_widths)
    ]
    return "  ".join(aligned_values).rstrip()


def _get_output_column_widths(columns: list[str]) -> list[int]:
    """Return shared display widths for header and data columns."""
    widths: list[int] = []
    for column in columns:
        label_width: int = max(map(len, column.split("\n")))
        if column == "index":
            data_width: int = 5
        elif "epoch" in column:
            data_width = 24
        else:
            data_width = 10
        widths.append(max(label_width, data_width))
    return widths


def _format_output_header(columns: list[str]) -> str:
    """Format a multi-line header with aligned column labels."""
    header_lines = [column.split("\n") for column in columns]
    column_widths = _get_output_column_widths(columns)
    lines: list[str] = []
    for line_index in range(max(map(len, header_lines))):
        line_values = [
            lines_for_column[line_index] if line_index < len(lines_for_column) else ""
            for lines_for_column in header_lines
        ]
        lines.append(
            "  ".join(
                f"{value:<{width}}" for value, width in zip(line_values, column_widths)
            ).rstrip()
        )
    return "\n".join(lines)


def print_header(
    include_time_difference: bool,
    verbose: bool = False,
    rtn: bool = False,
    include_comparison_epoch: bool = True,
) -> None:
    """Print the comparison result header with aligned columns.

    Parameters
    ----------
    include_time_difference : bool
        Whether to include the time-difference column.
    include_comparison_epoch : bool, optional
        Whether to include the comparison epoch column (default: True).
    verbose : bool, optional
        Whether to include component-wise difference columns (default: False).
    rtn : bool, optional
        Whether to include reference-frame RTN coordinates (default: False).
    """
    columns = _get_output_columns(
        include_time_difference,
        verbose,
        rtn,
        include_comparison_epoch,
    )
    print(_format_output_header(columns))


def print_results(
    index: int,
    comparison_result: ComparisonResult,
    verbose: bool = False,
    rtn: bool = False,
    include_comparison_epoch: bool = True,
) -> None:
    """Print one comparison result row with aligned columns.

    Parameters
    ----------
    index : int
        One-based index of the state in the comparison OEM.
    comparison_result : ComparisonResult
        Comparison results from :func:`compare_states`.
    include_comparison_epoch : bool, optional
        Whether to include the comparison epoch (default: True).
    verbose : bool, optional
        If True, print component-wise differences (default: False).
    rtn : bool, optional
        If True, print reference-frame RTN coordinates (default: False).
    """
    values: list[str] = [
        str(index),
        time_utils.datetime_to_iso8601(comparison_result.reference_epoch),
    ]
    if include_comparison_epoch:
        values.append(
            time_utils.datetime_to_iso8601(comparison_result.comparison_epoch)
        )
    if comparison_result.time_diff_s is not None:
        values.append(f"{comparison_result.time_diff_s:.6f}")
    values.extend(
        [
            f"{comparison_result.position_diff_magnitude_km:.3f}",
            f"{comparison_result.velocity_diff_magnitude_km_s:.6f}",
        ]
    )
    if verbose:
        values.extend(
            [
                f"{comparison_result.position_diff_km[0]:+.3f}",
                f"{comparison_result.position_diff_km[1]:+.3f}",
                f"{comparison_result.position_diff_km[2]:+.3f}",
                f"{comparison_result.velocity_diff_km_s[0]:+.6f}",
                f"{comparison_result.velocity_diff_km_s[1]:+.6f}",
                f"{comparison_result.velocity_diff_km_s[2]:+.6f}",
            ]
        )
    if rtn:
        values.extend(
            [
                f"{comparison_result.rtn_position_km[0]:+.3f}",
                f"{comparison_result.rtn_position_km[1]:+.3f}",
                f"{comparison_result.rtn_position_km[2]:+.3f}",
                f"{comparison_result.rtn_velocity_km_s[0]:+.6f}",
                f"{comparison_result.rtn_velocity_km_s[1]:+.6f}",
                f"{comparison_result.rtn_velocity_km_s[2]:+.6f}",
            ]
        )
    columns = _get_output_columns(
        comparison_result.time_diff_s is not None,
        verbose,
        rtn,
        include_comparison_epoch,
    )
    print(_format_output_row(values, columns))


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads OEM state vectors from files or
    stdin, compares corresponding OEM states, and prints a header followed by
    one tab-separated result row per comparison to stdout.
    Exits with status 1 on error.
    """
    args: argparse.Namespace = parse_arguments()

    try:
        reference_source: TextIO | str = (
            sys.stdin if args.reference_oem == "-" else args.reference_oem
        )
        comparison_source: TextIO | str = (
            sys.stdin if args.comparison_oem == "-" else args.comparison_oem
        )
        reference_states = read_states(reference_source)
        comparison_states = read_states(comparison_source)
        reference_oem = reference_states[0]
        has_time_window: bool = args.start is not None or args.stop is not None

        overlapping_time_range = _get_overlapping_time_range(
            reference_states, comparison_states
        )
        # Interpolation and explicit windows are only meaningful in shared data.
        if overlapping_time_range is None and (
            args.interpolate_ref or args.interpolate_data or has_time_window
        ):
            return

        if overlapping_time_range is not None:
            overlap_start, overlap_stop = overlapping_time_range
        else:
            overlap_start = overlap_stop = None

        if has_time_window:
            reference_epoch_s: float = reference_states[0][0]
            requested_start: float = (
                overlap_start
                if args.start is None
                else _resolve_time_bound(args.start, reference_epoch_s)
            )
            requested_stop: float = (
                overlap_stop
                if args.stop is None
                else _resolve_time_bound(args.stop, reference_epoch_s)
            )
            if requested_start > requested_stop:
                raise ValueError("--start must be earlier than or equal to --stop")
            overlap_start = max(overlap_start, requested_start)
            overlap_stop = min(overlap_stop, requested_stop)
            if overlap_start > overlap_stop:
                return

        # Each interpolator evaluates one history at epochs from the other.
        reference_interpolator = None
        if args.interpolate_ref:
            reference_interpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=INTERPOLATION_DEGREE
            )
            reference_interpolator.set_data(reference_states)

        comparison_interpolator = None
        if args.interpolate_data:
            comparison_interpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=INTERPOLATION_DEGREE
            )
            comparison_interpolator.set_data(comparison_states)

        comparison_results: list[ComparisonResult] = []
        comparison_pairs: Iterable[
            tuple[tuple[float, np.ndarray], tuple[float, np.ndarray]]
        ]
        # Choose query epochs according to which history, if any, is interpolated.
        if args.interpolate_data:
            comparison_pairs = [
                (state, comparison_states[0])
                for state in reference_states
                if overlap_start <= state[0] <= overlap_stop
            ]
        elif args.interpolate_ref:
            comparison_pairs = [
                (reference_oem, state)
                for state in comparison_states
                if overlap_start <= state[0] <= overlap_stop
            ]
        elif has_time_window:
            comparison_pairs = [
                (reference_state, comparison_state)
                for reference_state, comparison_state in zip(
                    reference_states, comparison_states
                )
                if overlap_start <= reference_state[0] <= overlap_stop
            ]
        else:
            comparison_pairs = zip(reference_states, comparison_states)

        for reference_state, comparison_state in comparison_pairs:
            try:
                comparison_results.append(
                    compare_states(
                        reference_state,
                        comparison_state,
                        reference_interpolator,
                        comparison_interpolator,
                    )
                )
            except ValueError as error:
                # A boundary sample can still fall outside the interpolator window.
                if (
                    (args.interpolate_ref or args.interpolate_data)
                    and str(error).endswith(
                        "outside the reference OEM interpolation range"
                    )
                ) or (
                    args.interpolate_data
                    and str(error).endswith(
                        "outside the comparison OEM interpolation range"
                    )
                ):
                    continue
                raise

        if not comparison_results:
            return

        print_header(
            include_time_difference=(
                reference_interpolator is None and comparison_interpolator is None
            ),
            include_comparison_epoch=(
                reference_interpolator is None and comparison_interpolator is None
            ),
            verbose=args.verbose,
            rtn=args.rtn,
        )
        for index, comparison_result in enumerate(comparison_results, start=1):
            print_results(
                index,
                comparison_result,
                include_comparison_epoch=(
                    reference_interpolator is None and comparison_interpolator is None
                ),
                verbose=args.verbose,
                rtn=args.rtn,
            )

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
