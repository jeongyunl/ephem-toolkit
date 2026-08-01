#!/usr/bin/env python3
"""Compare corresponding states from two OEM files.

Usage:
    python3 bin/diff_oem.py <reference_oem.oem> <comparison_oem.oem>
    python3 bin/diff_oem.py - <comparison_oem.oem>
    python3 bin/diff_oem.py <reference_oem.oem> -

The utility reports time, position, and velocity differences. Use ``-`` for one
stdin input.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.interpolator.lagrange as lagrange
import common.oem as oem
import common.time_utils as time_utils


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

    return ComparisonResult(
        reference_epoch=reference_epoch,
        comparison_epoch=comparison_epoch,
        time_diff_s=time_diff_s,
        position_diff_km=position_diff_km,
        position_diff_magnitude_km=position_diff_magnitude_km,
        velocity_diff_km_s=velocity_diff_km_s,
        velocity_diff_magnitude_km_s=velocity_diff_magnitude_km_s,
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``reference_oem``,
        ``comparison_oem``, ``verbose``, ``interpolate_ref``, and
        ``interpolate_data``.
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
    args = parser.parse_args()
    if args.reference_oem == "-" and args.comparison_oem == "-":
        parser.error("reference_oem and comparison_oem cannot both be '-'")
    return args


def print_results(
    index: int,
    comparison_result: ComparisonResult,
    verbose: bool = False,
) -> None:
    """Print comparison results.

    Parameters
    ----------
    index : int
        One-based index of the state in the comparison OEM.
    comparison_result : ComparisonResult
        Comparison results from :func:`compare_states`.
    verbose : bool, optional
        If True, print component-wise differences (default: False).
    """
    print(
        f"Comparison State {index}: "
        f"{time_utils.datetime_to_iso8601(comparison_result.comparison_epoch)}"
    )
    print(
        f"  Reference Epoch: "
        f"{time_utils.datetime_to_iso8601(comparison_result.reference_epoch)}"
    )
    if comparison_result.time_diff_s is not None:
        print(f"  Time Difference: {comparison_result.time_diff_s:.6f} seconds")
    print(
        "  Position Difference Magnitude: "
        f"{comparison_result.position_diff_magnitude_km:.9f} km"
    )
    if verbose:
        print(f"  ΔX: {comparison_result.position_diff_km[0]:+.9f} km")
        print(f"  ΔY: {comparison_result.position_diff_km[1]:+.9f} km")
        print(f"  ΔZ: {comparison_result.position_diff_km[2]:+.9f} km")
    print(
        "  Velocity Difference Magnitude: "
        f"{comparison_result.velocity_diff_magnitude_km_s:.12f} km/s"
    )
    if verbose:
        print(f"  ΔVX: {comparison_result.velocity_diff_km_s[0]:+.12f} km/s")
        print(f"  ΔVY: {comparison_result.velocity_diff_km_s[1]:+.12f} km/s")
        print(f"  ΔVZ: {comparison_result.velocity_diff_km_s[2]:+.12f} km/s")


def print_summary(results: list[ComparisonResult]) -> None:
    """Print statistical summaries for all state comparisons.

    Parameters
    ----------
    results : list[ComparisonResult]
        Comparison results to summarize.
    """
    position_magnitudes_km = np.array(
        [result.position_diff_magnitude_km for result in results]
    )
    velocity_magnitudes_km_s = np.array(
        [result.velocity_diff_magnitude_km_s for result in results]
    )

    print("\nStatistical Summary:")
    print("=" * 70)
    print(f"States compared: {len(results)}")
    if any(result.time_diff_s is not None for result in results):
        time_diffs_s = np.array(
            [result.time_diff_s for result in results if result.time_diff_s is not None]
        )
        summary_values = (
            ("Time Difference", time_diffs_s, "seconds"),
            ("Position Difference Magnitude", position_magnitudes_km, "km"),
            ("Velocity Difference Magnitude", velocity_magnitudes_km_s, "km/s"),
        )
    else:
        summary_values = (
            ("Position Difference Magnitude", position_magnitudes_km, "km"),
            ("Velocity Difference Magnitude", velocity_magnitudes_km_s, "km/s"),
        )

    for label, values, unit in summary_values:
        print(f"{label} ({unit}):")
        print(f"  Min:  {np.min(values):.12f}")
        print(f"  Max:  {np.max(values):.12f}")
        print(f"  Mean: {np.mean(values):.12f}")
        print(f"  Std:  {np.std(values):.12f}")
    print("=" * 70)


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads OEM state vectors from files or
    stdin, compares corresponding OEM states, and prints
    the differences and statistical summary to stdout.
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

        overlapping_time_range = _get_overlapping_time_range(
            reference_states, comparison_states
        )
        if overlapping_time_range is None and (
            args.interpolate_ref or args.interpolate_data
        ):
            return

        if overlapping_time_range is not None:
            overlap_start, overlap_stop = overlapping_time_range
        else:
            overlap_start = overlap_stop = None

        reference_interpolator = None
        if args.interpolate_ref:
            reference_interpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=8
            )
            reference_interpolator.set_data(reference_states)

        comparison_interpolator = None
        if args.interpolate_data:
            comparison_interpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=8
            )
            comparison_interpolator.set_data(comparison_states)

        comparison_results: list[ComparisonResult] = []
        comparison_pairs: Iterable[
            tuple[tuple[float, np.ndarray], tuple[float, np.ndarray]]
        ]
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

        for index, comparison_result in enumerate(comparison_results, start=1):
            print_results(index, comparison_result, verbose=args.verbose)
        print_summary(comparison_results)

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
