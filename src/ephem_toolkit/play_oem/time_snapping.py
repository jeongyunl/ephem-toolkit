"""Time-grid alignment helpers for play-oem plots and playback controls."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ephem_toolkit.core import time_utils


UTC_HALF_SECOND_S = 0.5


def snap_tt_s_to_utc_half_second(tt_s: float) -> float:
    """Snap TT seconds to the nearest half-second boundary in UTC.

    The epoch is shifted by the modeled TT−UTC offset, quantized on the UTC
    grid, then shifted back to TT. Halfway cases round toward the later instant.
    """
    if (
        isinstance(tt_s, bool)
        or not isinstance(tt_s, (int, float))
        or not math.isfinite(tt_s)
    ):
        raise ValueError("tt_s must be a finite number")
    tt = float(tt_s)
    tt_minus_utc = time_utils.tt_minus_utc_seconds(tt)
    utc_s_from_j2000 = tt - tt_minus_utc
    # J2000 is noon UTC. Shift to a midnight-based axis before quantizing so
    # this remains a civil UTC grid rather than a grid relative to TT seconds.
    utc_s_from_midnight = utc_s_from_j2000 + 43_200.0
    grid_index = math.floor(utc_s_from_midnight / UTC_HALF_SECOND_S + 0.5)
    snapped_utc_s_from_j2000 = grid_index * UTC_HALF_SECOND_S - 43_200.0
    return snapped_utc_s_from_j2000 + tt_minus_utc


@dataclass
class TimeSamplingPolicy:
    """Player-scoped policy for sampling time-series plot data."""

    align_to_utc_half_seconds: bool = True

    def sample(
        self,
        source_times_s: Sequence[float] | np.ndarray,
        source_values: Sequence[float] | np.ndarray,
        *,
        bounds_s: tuple[float, float],
        max_samples: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Sample a plot series using the current alignment preference."""
        return sample_time_series(
            source_times_s,
            source_values,
            bounds_s=bounds_s,
            max_samples=max_samples,
            align_to_utc_half_seconds=self.align_to_utc_half_seconds,
        )


def aligned_sample_times(
    start_s: float,
    stop_s: float,
    max_samples: int,
    *,
    align_to_utc_half_seconds: bool = True,
) -> np.ndarray:
    """Build a bounded regular time grid, optionally aligned to UTC half-seconds.

    With alignment disabled, the grid spans the range without UTC anchoring.
    When enabled, every adjacent pair is separated by a half-second multiple;
    a range too short to contain a grid point returns its start as one sample.
    """
    if (
        isinstance(start_s, bool)
        or isinstance(stop_s, bool)
        or not isinstance(start_s, (int, float))
        or not isinstance(stop_s, (int, float))
        or not math.isfinite(start_s)
        or not math.isfinite(stop_s)
    ):
        raise ValueError("sample bounds must be finite numbers")
    if start_s > stop_s:
        raise ValueError("start_s must not be after stop_s")
    if (
        isinstance(max_samples, bool)
        or not isinstance(max_samples, int)
        or max_samples < 1
    ):
        raise ValueError("max_samples must be a positive integer")
    if not isinstance(align_to_utc_half_seconds, bool):
        raise ValueError("align_to_utc_half_seconds must be true or false")

    start = float(start_s)
    stop = float(stop_s)
    if start == stop:
        return np.asarray([start], dtype=float)

    if not align_to_utc_half_seconds:
        count = min(
            max_samples,
            max(2, math.ceil((stop - start) / UTC_HALF_SECOND_S) + 1),
        )
        return np.linspace(start, stop, count, dtype=float)

    anchor = snap_tt_s_to_utc_half_second(start)
    target_step_s = (stop - start) / max(1, max_samples - 1)
    step_units = max(1, math.ceil(target_step_s / UTC_HALF_SECOND_S))
    step_s = step_units * UTC_HALF_SECOND_S

    while True:
        first_index = math.ceil((start - anchor) / step_s - 1e-12)
        last_index = math.floor((stop - anchor) / step_s + 1e-12)
        sample_count = last_index - first_index + 1
        if sample_count <= max_samples:
            break
        step_units += 1
        step_s = step_units * UTC_HALF_SECOND_S

    if sample_count <= 0:
        return np.asarray([start], dtype=float)
    indices = np.arange(first_index, last_index + 1, dtype=np.int64)
    return anchor + indices * step_s


def sample_time_series(
    source_times_s: Sequence[float] | np.ndarray,
    source_values: Sequence[float] | np.ndarray,
    *,
    bounds_s: tuple[float, float],
    max_samples: int,
    align_to_utc_half_seconds: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate values onto a bounded grid shared by Play-OEM time plots.

    ``source_values`` may be one-dimensional or have one or more columns.
    Non-finite rows are preserved as gaps in the output, so curves do not
    interpolate across missing data or explicit profile breaks.
    """
    times = np.asarray(source_times_s, dtype=float)
    values = np.asarray(source_values, dtype=float)
    if times.ndim != 1:
        raise ValueError("source_times_s must be one-dimensional")
    if values.ndim not in (1, 2) or values.shape[0] != times.size:
        raise ValueError("source_values must have one row per source time")
    if len(bounds_s) != 2:
        raise ValueError("bounds_s must contain a start and stop")
    if times.size == 0:
        return np.asarray([], dtype=float), np.empty_like(values)
    if (
        not np.isfinite(bounds_s[0])
        or not np.isfinite(bounds_s[1])
        or bounds_s[0] > bounds_s[1]
    ):
        raise ValueError("bounds_s must be finite and ordered")

    valid_times = np.isfinite(times)
    finite_indices = np.flatnonzero(valid_times)
    if not finite_indices.size:
        shape = (0,) if values.ndim == 1 else (0, values.shape[1])
        return np.asarray([], dtype=float), np.empty(shape, dtype=float)
    start = max(float(bounds_s[0]), float(times[finite_indices[0]]))
    stop = min(float(bounds_s[1]), float(times[finite_indices[-1]]))
    if start > stop:
        shape = (0,) if values.ndim == 1 else (0, values.shape[1])
        return np.asarray([], dtype=float), np.empty(shape, dtype=float)

    sample_times = aligned_sample_times(
        start,
        stop,
        max_samples,
        align_to_utc_half_seconds=align_to_utc_half_seconds,
    )
    sampled_shape = (
        (sample_times.size,)
        if values.ndim == 1
        else (sample_times.size, values.shape[1])
    )
    sampled_values = np.full(sampled_shape, np.nan, dtype=float)
    finite_values = np.isfinite(values)
    valid_rows = (
        valid_times & finite_values
        if values.ndim == 1
        else valid_times & np.all(finite_values, axis=1)
    )
    valid_indices = np.flatnonzero(valid_rows)
    run_breaks = np.flatnonzero(np.diff(valid_indices) > 1) + 1
    runs = np.split(valid_indices, run_breaks)
    for run in runs:
        if not run.size:
            continue
        run_times = times[run]
        grid_mask = (sample_times >= run_times[0]) & (sample_times <= run_times[-1])
        if run.size == 1:
            if sample_times.size == 1:
                grid_index = 0
            else:
                insertion = int(np.searchsorted(sample_times, run_times[0]))
                candidates = np.asarray(
                    [max(0, insertion - 1), min(insertion, sample_times.size - 1)]
                )
                grid_index = int(
                    candidates[
                        np.argmin(np.abs(sample_times[candidates] - run_times[0]))
                    ]
                )
            if grid_mask[grid_index] or (
                sample_times.size > 1
                and abs(sample_times[grid_index] - run_times[0])
                <= float(np.min(np.diff(sample_times))) * 0.5
            ):
                sampled_values[grid_index] = values[run[0]]
            continue
        if not np.any(grid_mask):
            continue
        grid = sample_times[grid_mask]
        if values.ndim == 1:
            sampled_values[grid_mask] = np.interp(grid, run_times, values[run])
        else:
            for column in range(values.shape[1]):
                sampled_values[grid_mask, column] = np.interp(
                    grid, run_times, values[run, column]
                )
    return sample_times, sampled_values
