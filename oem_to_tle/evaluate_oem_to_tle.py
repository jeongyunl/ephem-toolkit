#!/usr/bin/env python3
"""Evaluate oem_to_tle.py round-trip accuracy against an OEM reference.

Workflow:
  1. Read the OEM file from the test directory.
  2. Feed it to oem_to_tle.py to generate a TLE.
  3. Propagate the generated TLE with propagate_tle.py over the OEM time span.
  4. Compare propagated state vectors against the original OEM at matching epochs.
  5. Print position and velocity difference statistics.

Usage:
    python oem_to_tle/evaluate_oem_to_tle.py [--refinement none|cartesian|keplerian]
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.oem as oem
import common.time_utils as time_utils

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the round-trip evaluation.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``oem_file``, ``refinement``,
        ``duration``, and ``step``.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate oem_to_tle.py round-trip accuracy against an OEM reference."
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        default=str(PROJECT_ROOT / "test" / "data" / "ISS_2026-05-20.OEM"),
        help="Path to the reference OEM file (default: test/data/ISS_2026-05-20.OEM).",
    )
    parser.add_argument(
        "--refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        help=(
            "Refinement method passed to oem_to_tle.py. "
            "'cartesian' (default): SGP4 Cartesian state matching. "
            "'keplerian': osculating Keplerian element matching via common.kepler. "
            "'none': skip refinement."
        ),
    )
    parser.add_argument(
        "-d",
        "--duration",
        default=None,
        help="Propagation duration for propagate_tle.py (default: 1d). Accepts s/m/h/d suffix.",
    )
    parser.add_argument(
        "-s",
        "--step",
        default=None,
        help="Propagation step for propagate_tle.py (default: match OEM step).",
    )
    return parser.parse_args()


def run_oem_to_tle(
    oem_records: dict[float, np.ndarray], duration_s: float, refinement: str
) -> tuple[str, str, str]:
    """Run oem_to_tle.py on OEM records (limited to duration_s) via stdin.

    Parameters
    ----------
    oem_records : dict[float, np.ndarray]
        Dictionary mapping POSIX timestamps to state vectors (6-element arrays).
    duration_s : float
        Maximum time span in seconds to include in the fit input.
    refinement : str
        Refinement method passed to ``oem_to_tle.py`` (``"none"``,
        ``"cartesian"``, or ``"keplerian"``).

    Returns
    -------
    tuple[str, str, str]
        ``(tle_text, tle_line1, tle_line2)`` where *tle_text* is the full
        three-line TLE string.
    """
    # Convert dict to sorted list of (epoch_timestamp, state) tuples
    sorted_epochs = sorted(oem_records.keys())

    # Select records within the fit duration
    t0 = sorted_epochs[0]
    fit_epochs = [
        epoch_ts for epoch_ts in sorted_epochs if (epoch_ts - t0) <= duration_s
    ]
    if len(fit_epochs) < 2:
        fit_epochs = sorted_epochs[:2]

    # Format as simple state-vector lines for oem_to_tle.py stdin
    # oem_to_tle.py expects km and km/s (OEM standard), so convert from SI (m, m/s)
    input_lines: list[str] = []
    for epoch_ts in fit_epochs:
        state = oem_records[epoch_ts]
        pos = state[:3] / 1000.0  # Convert m → km
        vel = state[3:] / 1000.0  # Convert m/s → km/s
        # Convert POSIX timestamp to datetime for formatting
        epoch_dt = datetime.fromtimestamp(epoch_ts, tz=timezone.utc)
        epoch_str: str = epoch_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        input_lines.append(
            f"{epoch_str} {pos[0]:.12f} {pos[1]:.12f} {pos[2]:.12f} "
            f"{vel[0]:.12f} {vel[1]:.12f} {vel[2]:.12f}"
        )
    input_text: str = "\n".join(input_lines) + "\n"

    cmd: list[str] = [
        sys.executable,
        "-m",
        "oem_to_tle.oem_to_tle",
        "-",
        "--name",
        "GENERATED",
        "--satellite-number",
        "99999",
        "--classification",
        "U",
        "--int-designator-year",
        "0",
        "--int-designator-launch-number",
        "0",
        "--int-designator-piece",
        "A",
        "--refinement",
        refinement,
    ]

    env: dict[str, str] = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ":" + env.get("PYTHONPATH", "")

    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    if result.returncode != 0:
        print(f"ERROR: oem_to_tle.py failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Extract TLE lines from output
    lines: list[str] = result.stdout.strip().splitlines()
    tle_line1: str | None
    tle_line2: str | None
    tle_line1 = None
    tle_line2 = None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            tle_line1 = lines[i]
            tle_line2 = lines[i + 1]

    if tle_line1 is None or tle_line2 is None:
        print(
            f"ERROR: Could not find TLE in oem_to_tle.py output:\n{result.stdout[-500:]}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Print oem_to_tle summary (stderr lines from stdout)
    print("--- oem_to_tle.py summary ---")
    for line in lines:
        if line.startswith("  ") or line.startswith("Estimated"):
            print(line)
    print()

    return f"GENERATED\n{tle_line1}\n{tle_line2}\n", tle_line1, tle_line2


def run_propagate_tle(
    tle_text: str, duration_s: float, step_s: float
) -> list[tuple[datetime, list[float], list[float]]]:
    """Run propagate_tle.py on the generated TLE and return state records.

    Parameters
    ----------
    tle_text : str
        Three-line TLE string passed to ``propagate_tle.py`` via stdin.
    duration_s : float
        Propagation duration in seconds.
    step_s : float
        Output sampling interval in seconds.

    Returns
    -------
    list[tuple[datetime, list[float], list[float]]]
        List of ``(epoch_dt, pos_km, vel_km_s)`` tuples from the propagated
        state history.
    """
    cmd: list[str] = [
        sys.executable,
        str(PROJECT_ROOT / "propagation" / "propagate_tle.py"),
        "-d",
        f"{duration_s}s",
        "-s",
        f"{step_s}s",
    ]

    env: dict[str, str] = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ":" + env.get("PYTHONPATH", "")

    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd,
        input=tle_text,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    if result.returncode != 0:
        print(f"ERROR: propagate_tle.py failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    records: list[tuple[datetime, list[float], list[float]]] = []
    for line in result.stdout.strip().splitlines():
        parts: list[str] = line.strip().split()
        if len(parts) < 7:
            continue
        epoch_str: str = parts[0]
        if epoch_str.endswith("Z"):
            epoch_str = epoch_str[:-1]
        try:
            epoch: datetime = datetime.fromisoformat(epoch_str)
            # Add UTC timezone info to match OEM records
            if epoch.tzinfo is None:
                epoch = epoch.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        pos: list[float] = [float(parts[i]) for i in range(1, 4)]
        vel: list[float] = [float(parts[i]) for i in range(4, 7)]
        records.append((epoch, pos, vel))

    return records


def find_closest_epoch(
    target_epoch: datetime, records: list, max_dt_s: float = 30.0
) -> tuple[tuple | None, float | None]:
    """Find the record closest in time to target_epoch within max_dt_s.

    Parameters
    ----------
    target_epoch : datetime
        Reference epoch to search near.
    records : list
        List of ``(epoch_dt, pos_km, vel_km_s)`` tuples to search.
    max_dt_s : float
        Maximum allowed time difference in seconds (default: 30.0).

    Returns
    -------
    tuple[tuple | None, float | None]
        ``(best_record, best_dt_s)`` where *best_record* is the closest
        matching record or *None* if none is within *max_dt_s*.
    """
    best: tuple | None = None
    best_dt: float | None = None
    for rec in records:
        dt: float = abs((rec[0] - target_epoch).total_seconds())
        if dt > max_dt_s:
            continue
        if best_dt is None or dt < best_dt:
            best = rec
            best_dt = dt
    return best, best_dt


def norm3(v: list[float]) -> float:
    """Return the Euclidean norm of a 3-element vector.

    Parameters
    ----------
    v : list[float]
        3-element vector.

    Returns
    -------
    float
        Euclidean norm.
    """
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def evaluate_differences(
    oem_records: dict, prop_records: list
) -> tuple[list[float], list[float], int]:
    """Compare OEM reference states against propagated states at matching epochs.

    Parameters
    ----------
    oem_records : dict
        Reference state records as dict mapping epoch datetimes to state vectors.
    prop_records : list
        Propagated state records as ``(epoch_dt, pos_km, vel_km_s)`` tuples.

    Returns
    -------
    tuple[list[float], list[float], int]
        ``(pos_errors, vel_errors, matched_count)`` where *pos_errors* and
        *vel_errors* are lists of position and velocity error magnitudes in
        km and km/s respectively.
    """
    pos_errors: list[float] = []
    vel_errors: list[float] = []
    matched_count: int = 0

    for oem_epoch in sorted(oem_records.keys()):
        oem_state = oem_records[oem_epoch]
        # OEM states are in meters (SI); convert to km for comparison with
        # propagated output (which is in km from propagate_tle.py OEM output)
        oem_pos = oem_state[:3] / 1000.0  # Convert m → km
        oem_vel = oem_state[3:] / 1000.0  # Convert m/s → km/s

        match: tuple | None
        dt: float | None
        match, dt = find_closest_epoch(oem_epoch, prop_records, max_dt_s=5.0)
        if match is None:
            continue
        matched_count += 1
        _, prop_pos, prop_vel = match

        pos_diff: list[float] = [prop_pos[i] - oem_pos[i] for i in range(3)]
        vel_diff: list[float] = [prop_vel[i] - oem_vel[i] for i in range(3)]

        pos_errors.append(norm3(pos_diff))
        vel_errors.append(norm3(vel_diff))

    return pos_errors, vel_errors, matched_count


def print_statistics(
    pos_errors: list[float],
    vel_errors: list[float],
    matched_count: int,
    total_oem: int,
    duration_h: float,
) -> None:
    """Print position and velocity error statistics.

    Parameters
    ----------
    pos_errors : list[float]
        Position error magnitudes in km at each matched epoch.
    vel_errors : list[float]
        Velocity error magnitudes in km/s at each matched epoch.
    matched_count : int
        Number of OEM epochs successfully matched to propagated records.
    total_oem : int
        Total number of OEM reference epochs.
    duration_h : float
        Propagation span in hours, used for time-offset labels.
    """
    print(f"--- Evaluation Results ---")
    print(f"  OEM reference points:  {total_oem}")
    print(f"  Matched epochs:        {matched_count}")
    print(f"  Propagation span:      {duration_h:.2f} hours")
    print()

    if not pos_errors:
        print("  No matching epochs found!")
        return

    print(f"  Position error (km):")
    print(f"    Min:    {min(pos_errors):.6f}")
    print(f"    Max:    {max(pos_errors):.6f}")
    print(f"    Mean:   {sum(pos_errors)/len(pos_errors):.6f}")
    print(f"    RMS:    {math.sqrt(sum(e**2 for e in pos_errors)/len(pos_errors)):.6f}")
    print()
    print(f"  Velocity error (km/s):")
    print(f"    Min:    {min(vel_errors):.9f}")
    print(f"    Max:    {max(vel_errors):.9f}")
    print(f"    Mean:   {sum(vel_errors)/len(vel_errors):.9f}")
    print(f"    RMS:    {math.sqrt(sum(e**2 for e in vel_errors)/len(vel_errors)):.9f}")
    print()

    # Print error at selected time offsets
    if len(pos_errors) > 10:
        print(f"  Position error at selected times:")
        indices: list[int] = [
            0,
            len(pos_errors) // 4,
            len(pos_errors) // 2,
            3 * len(pos_errors) // 4,
            len(pos_errors) - 1,
        ]
        for idx in indices:
            t_h: float = (
                idx * duration_h / (len(pos_errors) - 1) if len(pos_errors) > 1 else 0
            )
            print(f"    t={t_h:6.2f}h:  {pos_errors[idx]:.3f} km")


def main() -> None:
    """Execute the TLE round-trip evaluation workflow.

    Reads an OEM file, generates a TLE using oem_to_tle.py, propagates it with
    propagate_tle.py, and compares the propagated states against the original
    OEM reference to compute position and velocity error statistics.
    """
    args: argparse.Namespace = parse_args()
    oem_path: Path = Path(args.oem_file)

    if not oem_path.exists():
        print(f"ERROR: OEM file not found: {oem_path}", file=sys.stderr)
        sys.exit(1)

    print(f"=== oem_to_tle.py Round-Trip Evaluation ===")
    print(f"  OEM file: {oem_path.name}")
    print(f"  Refinement: {args.refinement}")
    print()

    # Step 1: Read OEM reference
    header: dict
    meta: dict
    oem_records_float: dict
    header, meta, oem_records_float = oem.read_oem(oem_path)
    if len(oem_records_float) < 2:
        print("ERROR: OEM file has fewer than 2 state vectors.", file=sys.stderr)
        sys.exit(1)

    # oem_records_float is now dict[float, np.ndarray] (POSIX timestamps)
    # Convert to dict[datetime, np.ndarray] for compatibility
    oem_records: dict = {
        datetime.fromtimestamp(ts, tz=timezone.utc): state
        for ts, state in oem_records_float.items()
    }

    sorted_epochs: list = sorted(oem_records.keys())
    oem_start: datetime = sorted_epochs[0]
    oem_end: datetime = sorted_epochs[-1]
    oem_span_s: float = (oem_end - oem_start).total_seconds()
    oem_step_s: float = (
        (sorted_epochs[1] - sorted_epochs[0]).total_seconds()
        if len(sorted_epochs) > 1
        else 240.0
    )

    print(f"  OEM span:       {oem_span_s/3600:.2f} hours ({len(oem_records)} points)")
    print(f"  OEM step:       {oem_step_s:.0f} s")
    print()

    # Parse duration early so we can pass it to oem_to_tle
    duration_s: float = (
        time_utils.parse_duration_to_seconds(args.duration)
        if args.duration
        else 86400.0
    )

    # Step 2: Generate TLE from OEM (limited to duration)
    print("Step 1: Generating TLE from OEM with oem_to_tle.py...")
    tle_text: str
    line1: str
    line2: str
    tle_text, line1, line2 = run_oem_to_tle(
        oem_records_float, duration_s, args.refinement
    )
    print(f"  Generated TLE:")
    print(f"    {line1}")
    print(f"    {line2}")
    print()

    # Step 3: Propagate generated TLE over the evaluation span
    step_s: float = (
        time_utils.parse_duration_to_seconds(args.step) if args.step else oem_step_s
    )

    print(
        f"Step 2: Propagating generated TLE for {duration_s/3600:.2f}h at {step_s:.0f}s steps..."
    )
    prop_records: list = run_propagate_tle(tle_text, duration_s, step_s)
    print(f"  Propagated {len(prop_records)} state vectors.")
    print()

    # Step 4: Evaluate differences
    print("Step 3: Evaluating position/velocity differences...")
    pos_errors: list[float]
    vel_errors: list[float]
    matched_count: int
    pos_errors, vel_errors, matched_count = evaluate_differences(
        oem_records, prop_records
    )
    print()

    duration_h: float = duration_s / 3600.0
    print_statistics(
        pos_errors, vel_errors, matched_count, len(oem_records), duration_h
    )


if __name__ == "__main__":
    main()
