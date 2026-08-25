"""Utility functions for OEM comparison operations."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import numpy as np

import ephem_toolkit.core.interpolator as interpolator
import ephem_toolkit.core.time_utils as time_utils

from .comparison import compare_states
from .data_structures import ComparisonResult
from .types import State, StatePair
from .debug import debug_print, debug_format_epoch, debug_print_time_range


def find_overlapping_time_range(
    reference_states: list[tuple[float, np.ndarray]],
    comparison_states: list[tuple[float, np.ndarray]],
) -> tuple[float, float] | None:
    """Find the inclusive time range shared by two ordered state lists.

    Parameters
    ----------
    reference_states : list[tuple[float, np.ndarray]]
        Ordered list of (epoch, state) tuples from reference OEM.
    comparison_states : list[tuple[float, np.ndarray]]
        Ordered list of (epoch, state) tuples from comparison OEM.

    Returns
    -------
    tuple[float, float] | None
        Tuple of (start_epoch, stop_epoch) in POSIX seconds, or None if no overlap.
    """
    overlap_start: float = max(reference_states[0][0], comparison_states[0][0])
    overlap_stop: float = min(reference_states[-1][0], comparison_states[-1][0])
    debug_print_time_range(
        "find_overlapping_time_range: ref data",
        reference_states[0][0],
        reference_states[-1][0],
    )
    debug_print_time_range(
        "find_overlapping_time_range: cmp data",
        comparison_states[0][0],
        comparison_states[-1][0],
    )
    if overlap_start > overlap_stop:
        debug_print("find_overlapping_time_range: no overlap")
        return None
    debug_print_time_range(
        "find_overlapping_time_range: overlap", overlap_start, overlap_stop
    )
    return overlap_start, overlap_stop


def resolve_time_bound(value: str, reference_epoch_s: float) -> float:
    """Resolve an absolute or reference-relative time bound to POSIX seconds.

    Parameters
    ----------
    value : str
        ISO 8601 timestamp or duration string.
    reference_epoch_s : float
        Reference epoch in POSIX seconds for relative time calculations.

    Returns
    -------
    float
        Resolved time bound in POSIX seconds.
    """
    parsed_value: datetime | timedelta = time_utils.parse_time_or_duration(value)
    reference_datetime: datetime = datetime.fromtimestamp(
        reference_epoch_s, tz=timezone.utc
    )
    if isinstance(parsed_value, timedelta):
        parsed_value = reference_datetime + parsed_value
    resolved = parsed_value.timestamp()
    debug_print(
        f"resolve_time_bound: input='{value}', "
        f"reference_epoch={debug_format_epoch(reference_epoch_s)}, "
        f"resolved={debug_format_epoch(resolved)}"
    )
    return resolved


def parse_rotation_fit_span(value: str) -> float:
    """Parse a positive duration used for fitting the optional rotation.

    Parameters
    ----------
    value : str
        Duration string to parse.

    Returns
    -------
    float
        Duration in seconds.
    """
    return time_utils.parse_duration_to_seconds(value)


def build_comparison_pairs(
    reference_states: list[State],
    comparison_states: list[State],
    has_time_window: bool,
    overlap_start: float | None,
    overlap_stop: float | None,
) -> list[StatePair]:
    """Build comparison query pairs for interpolation.

    Each pair contains a reference state and the first comparison state as a
    placeholder; the comparison interpolator evaluates at the reference epoch.

    Parameters
    ----------
    reference_states : list[State]
        List of reference state tuples (epoch, state_vector).
    comparison_states : list[State]
        List of comparison state tuples (epoch, state_vector).
    has_time_window : bool
        Whether a time window filter is active.
    overlap_start : float | None
        Start of overlap window in POSIX seconds, or None.
    overlap_stop : float | None
        Stop of overlap window in POSIX seconds, or None.

    Returns
    -------
    list[StatePair]
        List of (reference_state, comparison_state) pairs for comparison.
    """
    debug_print(
        f"build_comparison_pairs: "
        f"ref_states={len(reference_states)}, cmp_states={len(comparison_states)}, "
        f"has_time_window={has_time_window}, "
        f"overlap=[{debug_format_epoch(overlap_start)} .. {debug_format_epoch(overlap_stop)}]"
    )
    pairs = [
        (state, comparison_states[0])
        for state in reference_states
        if not has_time_window or overlap_start <= state[0] <= overlap_stop
    ]
    debug_print(f"build_comparison_pairs: {len(pairs)} pairs")
    return pairs


def compare_pairs(
    comparison_pairs: list[StatePair],
    reference_interpolator: interpolator.Interpolator,
    comparison_interpolator: interpolator.Interpolator,
    comparison_rotation_matrix: np.ndarray | None,
) -> list[tuple[float, ComparisonResult | None]]:
    """Evaluate selected state pairs with an optional comparison rotation.

    Parameters
    ----------
    comparison_pairs : list[StatePair]
        List of (reference_state, comparison_state) pairs to compare.
    reference_interpolator : interpolator.Interpolator
        Interpolator for reference states.
    comparison_interpolator : interpolator.Interpolator
        Interpolator for comparison states.
    comparison_rotation_matrix : np.ndarray | None
        Optional rotation matrix to apply to comparison states.

    Returns
    -------
    list[tuple[float, ComparisonResult | None]]
        List of (epoch, comparison_result) tuples. Result is None if interpolation failed.
    """
    debug_print(
        f"compare_pairs: {len(comparison_pairs)} pairs, "
        f"rotation={'yes' if comparison_rotation_matrix is not None else 'no'}"
    )
    if comparison_pairs:
        first_ref_epoch = comparison_pairs[0][0][0]
        last_ref_epoch = comparison_pairs[-1][0][0]
        first_cmp_epoch = comparison_pairs[0][1][0]
        last_cmp_epoch = comparison_pairs[-1][1][0]
        debug_print_time_range(
            "compare_pairs: ref data time range", first_ref_epoch, last_ref_epoch
        )
        debug_print_time_range(
            "compare_pairs: cmp data time range", first_cmp_epoch, last_cmp_epoch
        )
    comparison_results: list[tuple[float, ComparisonResult | None]] = []
    for reference_state, comparison_state in comparison_pairs:
        query_epoch_s = reference_state[0]
        try:
            comparison_results.append(
                (
                    query_epoch_s,
                    compare_states(
                        reference_state,
                        comparison_state,
                        reference_interpolator,
                        comparison_interpolator,
                        comparison_rotation_matrix,
                    ),
                )
            )
        except ValueError as error:
            # A boundary sample can still fall outside the interpolator window.
            error_message = str(error)
            if error_message.endswith(
                "outside the reference OEM interpolation range"
            ) or error_message.endswith(
                "outside the comparison OEM interpolation range"
            ):
                comparison_results.append((query_epoch_s, None))
                continue
            raise
    return comparison_results
