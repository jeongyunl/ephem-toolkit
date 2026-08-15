#!/usr/bin/env python3
"""Evaluate interpolation accuracy near the domain boundaries.

This script compares interpolated states against a reference ephemeris or state
series at times that lie close to the first and last sample in the source data.
It is designed to highlight boundary degradation for polynomial interpolators,
which is often more severe than errors in the interior of the data range.

Examples
--------
    evaluate-interpolator-accuracy source.oem --reference reference.oem \
        --interpolate-type hermite,5

    evaluate-interpolator-accuracy source.oem --step-size 60s \
        --interpolate-type chebyshev,7
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)


def _as_state_list(states: Iterable[tuple[float, np.ndarray]]) -> list[tuple[float, np.ndarray]]:
    """Normalize a state series into a sorted list of (timestamp, state) tuples."""
    normalized = sorted(states, key=lambda item: item[0])
    return [(float(ts), np.asarray(state, dtype=float).copy()) for ts, state in normalized]


def _boundary_query_times(
    states: list[tuple[float, np.ndarray]],
    step_size_s: float,
    boundary_points: int,
) -> list[float]:
    """Return query times near the first and last boundary of the dataset."""
    if len(states) < 2:
        return []

    first_ts = states[0][0]
    last_ts = states[-1][0]
    query_times: list[float] = []

    for offset in range(1, boundary_points + 1):
        start_time = first_ts + offset * step_size_s * 0.5
        stop_time = last_ts - offset * step_size_s * 0.5
        if start_time < stop_time:
            query_times.append(start_time)
            query_times.append(stop_time)

    return sorted(set(query_times))


def evaluate_boundary_accuracy(
    states: list[tuple[float, np.ndarray]],
    interpolation_spec: InterpolationSpec,
    step_size: float | None = None,
    boundary_points: int = 8,
    reference_states: list[tuple[float, np.ndarray]] | None = None,
    boundary_mode: str = "centered",
    boundary_window_extension: int = 0,
) -> dict[str, float | int | str | InterpolationSpec]:
    """Evaluate interpolation error in a narrow region near the data boundaries.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        Source state series used to build the interpolator.
    interpolation_spec : InterpolationSpec
        Interpolation type and degree to evaluate.
    step_size : float | None, optional
        Query spacing in seconds. If omitted, the median sample spacing is used.
    boundary_points : int, optional
        Number of boundary offsets to probe on each side.
    reference_states : list[tuple[float, np.ndarray]] | None, optional
        High-accuracy reference state series. If omitted, the source states are used
        as the reference and the nearest state is compared against the interpolated
        value at mid-interval query times.

    Returns
    -------
    dict
        Summary metrics with keys such as ``n_boundary_points``, ``max_pos_err_m``,
        ``rms_pos_err_m``, ``max_vel_err_m_s`` and ``rms_vel_err_m_s``.
    """
    if not states:
        raise ValueError("states must contain at least one sample")

    normalized_states = _as_state_list(states)
    reference = _as_state_list(reference_states if reference_states is not None else normalized_states)

    if step_size is None:
        time_deltas = [b[0] - a[0] for a, b in zip(normalized_states, normalized_states[1:])]
        if not time_deltas:
            raise ValueError("states must contain at least two timestamps")
        step_size = float(np.median(time_deltas))
    step_size = float(step_size)
    if step_size <= 0.0:
        raise ValueError("step_size must be positive")

    if boundary_points <= 0:
        raise ValueError("boundary_points must be positive")

    state_dim = len(normalized_states[0][1])
    query_times = _boundary_query_times(normalized_states, step_size, boundary_points)
    if not query_times:
        raise ValueError("No boundary query times available from the supplied states")

    reference_map = {float(ts): np.asarray(state, dtype=float).copy() for ts, state in reference}

    interpolator = InterpolatorFactory.create(
        interpolation_spec,
        dimension=state_dim,
        is_cartesian_state=state_dim == 6,
        data=normalized_states,
        boundary_mode=boundary_mode,
        boundary_window_extension=boundary_window_extension,
    )

    pos_errors: list[float] = []
    vel_errors: list[float] = []
    worst_time_s: float | None = None
    worst_pos_err_m: float = 0.0
    worst_vel_err_m_s: float = 0.0

    for query_ts in query_times:
        if query_ts < normalized_states[0][0] or query_ts > normalized_states[-1][0]:
            continue

        interpolated = interpolator.interpolate(query_ts)
        if interpolated is None:
            continue

        ref_state = None
        if query_ts in reference_map:
            ref_state = reference_map[query_ts]
        else:
            ref_source = sorted(reference_map.items(), key=lambda item: abs(item[0] - query_ts))
            if not ref_source:
                continue
            ref_state = ref_source[0][1]

        pos_err = float(np.linalg.norm(interpolated[:3] - ref_state[:3]))
        vel_err = float(np.linalg.norm(interpolated[3:6] - ref_state[3:6]))

        pos_errors.append(pos_err)
        vel_errors.append(vel_err)

        if pos_err > worst_pos_err_m:
            worst_pos_err_m = pos_err
            worst_time_s = query_ts
        if vel_err > worst_vel_err_m_s:
            worst_vel_err_m_s = vel_err

    if not pos_errors:
        raise ValueError("No valid interpolated boundary points were evaluated")

    pos_array = np.asarray(pos_errors, dtype=float)
    vel_array = np.asarray(vel_errors, dtype=float)

    return {
        "spec": interpolation_spec,
        "n_boundary_points": int(len(pos_errors)),
        "max_pos_err_m": float(np.max(pos_array)),
        "rms_pos_err_m": float(np.sqrt(np.mean(pos_array**2))),
        "mean_pos_err_m": float(np.mean(pos_array)),
        "std_pos_err_m": float(np.std(pos_array)),
        "max_vel_err_m_s": float(np.max(vel_array)),
        "rms_vel_err_m_s": float(np.sqrt(np.mean(vel_array**2))),
        "mean_vel_err_m_s": float(np.mean(vel_array)),
        "std_vel_err_m_s": float(np.std(vel_array)),
        "worst_boundary_time_s": float(worst_time_s) if worst_time_s is not None else float("nan"),
        "worst_pos_err_m": float(worst_pos_err_m),
        "worst_vel_err_m_s": float(worst_vel_err_m_s),
        "step_size_s": float(step_size),
    }


def _spec_id(spec: InterpolationSpec) -> str:
    return f"{spec.interp_type.value},deg={spec.degree}"


def _parse_interpolation_spec(value: str) -> InterpolationSpec:
    """Parse a value like 'hermite,5' or 'chebyshev,7'."""
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("Interpolation type cannot be empty")

    if "," in text:
        name, degree_text = [part.strip() for part in text.split(",", 1)]
    else:
        name, degree_text = text, None

    normalized = name.lower().replace("_", "")
    if normalized == "hermitesliding":
        interp_type = InterpolationType.HERMITE
    elif normalized == "hermite":
        interp_type = InterpolationType.HERMITE
    elif normalized == "chebyshev":
        interp_type = InterpolationType.CHEBYSHEV
    elif normalized == "lagrange":
        interp_type = InterpolationType.LAGRANGE
    else:
        raise argparse.ArgumentTypeError(
            f"Unsupported interpolation type '{value}'. Supported values are: "
            "hermite, chebyshev, lagrange."
        )

    degree = None if degree_text is None else int(degree_text)
    return InterpolationSpec(interp_type=interp_type, degree=degree)


def _read_oem_states(path: Path) -> list[tuple[float, np.ndarray]]:
    if not path.exists():
        raise FileNotFoundError(f"OEM file not found: {path}")
    return CcsdsOem.read(str(path)).states


def _print_summary(results: dict[str, float | int | str | InterpolationSpec]) -> None:
    spec = results["spec"]
    print(f"Interpolation: {_spec_id(spec)}")
    print(f"Boundary samples evaluated: {results['n_boundary_points']}")
    print(f"Query spacing: {results['step_size_s']:.3f} s")
    print(f"Max position error: {results['max_pos_err_m']:.6e} m")
    print(f"RMS position error: {results['rms_pos_err_m']:.6e} m")
    print(f"Mean position error: {results['mean_pos_err_m']:.6e} m")
    print(f"Max velocity error: {results['max_vel_err_m_s']:.6e} m/s")
    print(f"RMS velocity error: {results['rms_vel_err_m_s']:.6e} m/s")
    print(
        "Worst boundary epoch: "
        f"{results['worst_boundary_time_s']:.3f} s"
        if math.isfinite(float(results["worst_boundary_time_s"]))
        else "Worst boundary epoch: n/a"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate interpolation accuracy near the boundaries of an OEM ephemeris.",
    )
    parser.add_argument("source_oem", type=Path, help="OEM file used to build the interpolator.")
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="Optional higher-accuracy OEM file to use as the truth reference.",
    )
    parser.add_argument(
        "--interpolate-type",
        type=_parse_interpolation_spec,
        default=InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=5),
        help="Interpolation specification in the form 'type[,degree]'; default: hermite,5",
    )
    parser.add_argument(
        "--step-size",
        type=float,
        default=None,
        help="Optional query spacing in seconds. Defaults to the median sample spacing.",
    )
    parser.add_argument(
        "--boundary-points",
        type=int,
        default=8,
        help="Number of mid-interval query points to test on each side of the data range.",
    )
    parser.add_argument(
        "--boundary-mode",
        type=str,
        default="centered",
        choices=["centered", "widen", "edge", "compact"],
        help="Hermite boundary window strategy: centered, widen, edge, or compact.",
    )
    parser.add_argument(
        "--boundary-window-extension",
        type=int,
        default=0,
        help="Extra points used by widen/edge/compact boundary strategies.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    source_states = _read_oem_states(args.source_oem)
    reference_states = _read_oem_states(args.reference) if args.reference is not None else None

    try:
        results = evaluate_boundary_accuracy(
            states=source_states,
            interpolation_spec=args.interpolate_type,
            step_size=args.step_size,
            boundary_points=args.boundary_points,
            reference_states=reference_states,
            boundary_mode=args.boundary_mode,
            boundary_window_extension=args.boundary_window_extension,
        )
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
