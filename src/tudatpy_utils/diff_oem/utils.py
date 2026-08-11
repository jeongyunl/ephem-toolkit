"""Utility functions for OEM comparison operations."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from tudatpy_utils.core.interpolator import lagrange
from tudatpy_utils.core import time_utils

from .comparison import compare_states
from .data_structures import ComparisonResult
from .types import State, StatePair


def get_overlapping_time_range(
    reference_states: list[tuple[float, np.ndarray]],
    comparison_states: list[tuple[float, np.ndarray]],
) -> tuple[float, float] | None:
    """Return the inclusive time range shared by two ordered state lists."""
    overlap_start: float = max(reference_states[0][0], comparison_states[0][0])
    overlap_stop: float = min(reference_states[-1][0], comparison_states[-1][0])
    if overlap_start > overlap_stop:
        return None
    return overlap_start, overlap_stop


def resolve_time_bound(value: str, reference_epoch_s: float) -> float:
    """Resolve an absolute or reference-relative time bound to POSIX seconds."""
    parsed_value: datetime | timedelta = time_utils.parse_time_or_duration(value)
    reference_datetime: datetime = datetime.fromtimestamp(
        reference_epoch_s, tz=timezone.utc
    )
    if isinstance(parsed_value, timedelta):
        parsed_value = reference_datetime + parsed_value
    return parsed_value.timestamp()


def parse_rotation_fit_span(value: str) -> float:
    """Parse a positive duration used for fitting the optional rotation."""
    return time_utils.parse_duration_to_seconds(value)


def format_epoch(epoch_s: float | None) -> str:
    """Format a POSIX epoch for debug output."""
    if epoch_s is None:
        return "none"
    epoch = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    return time_utils.datetime_to_iso8601(epoch)


def print_debug_range(
    label: str,
    start_epoch_s: float | None,
    stop_epoch_s: float | None,
) -> None:
    """Print one labeled time range to stderr."""
    print(
        f"[diff_oem] {label}: start={format_epoch(start_epoch_s)}, "
        f"stop={format_epoch(stop_epoch_s)}",
        file=sys.stderr,
    )


def build_comparison_pairs(
    reference_states: list[State],
    comparison_states: list[State],
    reference_oem: State,
    interpolate_ref: bool,
    interpolate_data: bool,
    has_time_window: bool,
    overlap_start: float | None,
    overlap_stop: float | None,
) -> list[StatePair]:
    """Build comparison query pairs from interpolation and time-window options."""
    if interpolate_data:
        return [
            (state, comparison_states[0])
            for state in reference_states
            if not has_time_window or overlap_start <= state[0] <= overlap_stop
        ]
    if interpolate_ref:
        return [
            (reference_oem, state)
            for state in comparison_states
            if not has_time_window or overlap_start <= state[0] <= overlap_stop
        ]
    if has_time_window:
        return [
            (reference_state, comparison_state)
            for reference_state, comparison_state in zip(
                reference_states, comparison_states
            )
            if overlap_start <= reference_state[0] <= overlap_stop
        ]
    return list(zip(reference_states, comparison_states))


def compare_pairs(
    comparison_pairs: list[StatePair],
    reference_interpolator: lagrange.LagrangeInterpolator | None,
    comparison_interpolator: lagrange.LagrangeInterpolator | None,
    comparison_rotation_matrix: np.ndarray | None,
) -> list[tuple[float, ComparisonResult | None]]:
    """Evaluate selected state pairs with an optional comparison rotation."""
    comparison_results: list[tuple[float, ComparisonResult | None]] = []
    for reference_state, comparison_state in comparison_pairs:
        query_epoch_s = (
            comparison_state[0]
            if reference_interpolator is not None and comparison_interpolator is None
            else reference_state[0]
        )
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
            if (
                (
                    reference_interpolator is not None
                    or comparison_interpolator is not None
                )
                and str(error).endswith("outside the reference OEM interpolation range")
            ) or (
                comparison_interpolator is not None
                and str(error).endswith(
                    "outside the comparison OEM interpolation range"
                )
            ):
                comparison_results.append((query_epoch_s, None))
                continue
            raise
    return comparison_results
