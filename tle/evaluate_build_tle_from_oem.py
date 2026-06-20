#!/usr/bin/env python3
"""Evaluate build_tle.py round-trip accuracy against an OEM reference.

Workflow:
  1. Read the OEM file from the test directory.
  2. Feed it to build_tle.py to generate a TLE.
  3. Propagate the generated TLE with propagate_tle.py over the OEM time span.
  4. Compare propagated state vectors against the original OEM at matching epochs.
  5. Print position and velocity difference statistics.

Usage:
    python misc/evaluate_build_tle_from_oem.py [--refinement none|cartesian|keplerian]
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import common.oem as oem
from common.common import parse_duration_to_seconds, parse_step_to_seconds


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate build_tle.py round-trip accuracy against an OEM reference."
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        default=str(PROJECT_ROOT / "test" / "ISS_2026-05-20.OEM"),
        help="Path to the reference OEM file (default: test/ISS_2026-05-20.OEM).",
    )
    parser.add_argument(
        "--refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        help=(
            "Refinement method passed to build_tle.py. "
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


def read_oem_states(oem_path):
    """Read OEM and return sorted list of (datetime, pos_km[3], vel_km_s[3])."""
    header, meta, states = oem.read_oem(oem_path)
    records = []
    for epoch in sorted(states):
        sv = states[epoch]
        if len(sv) < 6:
            continue
        if isinstance(epoch, (int, float)):
            epoch = datetime.fromtimestamp(epoch, tz=timezone.utc)
        records.append(
            (epoch, [float(sv[i]) for i in range(3)], [float(sv[i]) for i in range(3, 6)])
        )
    return records, header, meta


def run_build_tle(oem_records, duration_s, refinement):
    """Run build_tle.py on OEM records (limited to duration_s) via stdin."""
    # Select records within the fit duration
    t0 = oem_records[0][0]
    if isinstance(t0, (int, float)):
        fit_records = [rec for rec in oem_records if rec[0] - t0 <= duration_s]
    else:
        fit_records = [rec for rec in oem_records if (rec[0] - t0).total_seconds() <= duration_s]
    if len(fit_records) < 2:
        fit_records = oem_records[:2]

    # Format as simple state-vector lines for build_tle.py stdin
    input_lines = []
    for epoch, pos, vel in fit_records:
        if isinstance(epoch, (int, float)):
            epoch = datetime.fromtimestamp(epoch, tz=timezone.utc)
        epoch_str = epoch.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        input_lines.append(
            f"{epoch_str} {pos[0]:.12f} {pos[1]:.12f} {pos[2]:.12f} "
            f"{vel[0]:.12f} {vel[1]:.12f} {vel[2]:.12f}"
        )
    input_text = "\n".join(input_lines) + "\n"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tle" / "build_tle.py"),
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

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ":" + env.get("PYTHONPATH", "")

    result = subprocess.run(
        cmd, input=input_text, capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env
    )
    if result.returncode != 0:
        print(f"ERROR: build_tle.py failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Extract TLE lines from output
    lines = result.stdout.strip().splitlines()
    tle_line1 = None
    tle_line2 = None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            tle_line1 = lines[i]
            tle_line2 = lines[i + 1]

    if tle_line1 is None or tle_line2 is None:
        print(
            f"ERROR: Could not find TLE in build_tle.py output:\n{result.stdout[-500:]}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Print build_tle summary (stderr lines from stdout)
    print("--- build_tle.py summary ---")
    for line in lines:
        if line.startswith("  ") or line.startswith("Estimated"):
            print(line)
    print()

    return f"GENERATED\n{tle_line1}\n{tle_line2}\n", tle_line1, tle_line2


def run_propagate_tle(tle_text, duration_s, step_s):
    """Run propagate_tle.py on the generated TLE and return state records."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "propagation" / "propagate_tle.py"),
        "-d",
        f"{duration_s}s",
        "-s",
        f"{step_s}s",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ":" + env.get("PYTHONPATH", "")

    result = subprocess.run(
        cmd, input=tle_text, capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env
    )
    if result.returncode != 0:
        print(f"ERROR: propagate_tle.py failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    records = []
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split()
        if len(parts) < 7:
            continue
        epoch_str = parts[0]
        if epoch_str.endswith("Z"):
            epoch_str = epoch_str[:-1]
        try:
            epoch = datetime.fromisoformat(epoch_str)
        except ValueError:
            continue
        pos = [float(parts[i]) for i in range(1, 4)]
        vel = [float(parts[i]) for i in range(4, 7)]
        records.append((epoch, pos, vel))

    return records


def find_closest_epoch(target_epoch, records, max_dt_s=30.0):
    """Find the record closest in time to target_epoch within max_dt_s."""
    best = None
    best_dt = None
    for rec in records:
        dt = abs((rec[0] - target_epoch).total_seconds())
        if dt > max_dt_s:
            continue
        if best_dt is None or dt < best_dt:
            best = rec
            best_dt = dt
    return best, best_dt


def norm3(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def evaluate_differences(oem_records, prop_records):
    """Compare OEM reference states against propagated states at matching epochs."""
    pos_errors = []
    vel_errors = []
    matched_count = 0

    for oem_epoch, oem_pos, oem_vel in oem_records:
        match, dt = find_closest_epoch(oem_epoch, prop_records, max_dt_s=5.0)
        if match is None:
            continue
        matched_count += 1
        _, prop_pos, prop_vel = match

        pos_diff = [prop_pos[i] - oem_pos[i] for i in range(3)]
        vel_diff = [prop_vel[i] - oem_vel[i] for i in range(3)]

        pos_errors.append(norm3(pos_diff))
        vel_errors.append(norm3(vel_diff))

    return pos_errors, vel_errors, matched_count


def print_statistics(pos_errors, vel_errors, matched_count, total_oem, duration_h):
    """Print position and velocity error statistics."""
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
        indices = [
            0,
            len(pos_errors) // 4,
            len(pos_errors) // 2,
            3 * len(pos_errors) // 4,
            len(pos_errors) - 1,
        ]
        for idx in indices:
            t_h = idx * duration_h / (len(pos_errors) - 1) if len(pos_errors) > 1 else 0
            print(f"    t={t_h:6.2f}h:  {pos_errors[idx]:.3f} km")


def main():
    args = parse_args()
    oem_path = Path(args.oem_file)

    if not oem_path.exists():
        print(f"ERROR: OEM file not found: {oem_path}", file=sys.stderr)
        sys.exit(1)

    print(f"=== build_tle.py Round-Trip Evaluation ===")
    print(f"  OEM file: {oem_path.name}")
    print(f"  Refinement: {args.refinement}")
    print()

    # Step 1: Read OEM reference
    oem_records, header, meta = read_oem_states(oem_path)
    if len(oem_records) < 2:
        print("ERROR: OEM file has fewer than 2 state vectors.", file=sys.stderr)
        sys.exit(1)

    oem_start = oem_records[0][0]
    oem_end = oem_records[-1][0]
    oem_span_s = (oem_end - oem_start).total_seconds()
    oem_step_s = (
        (oem_records[1][0] - oem_records[0][0]).total_seconds() if len(oem_records) > 1 else 240.0
    )

    print(f"  OEM span:       {oem_span_s/3600:.2f} hours ({len(oem_records)} points)")
    print(f"  OEM step:       {oem_step_s:.0f} s")
    print()

    # Parse duration early so we can pass it to build_tle
    duration_s = parse_duration_to_seconds(args.duration) if args.duration else 86400.0

    # Step 2: Generate TLE from OEM (limited to duration)
    print("Step 1: Generating TLE from OEM with build_tle.py...")
    tle_text, line1, line2 = run_build_tle(oem_records, duration_s, args.refinement)
    print(f"  Generated TLE:")
    print(f"    {line1}")
    print(f"    {line2}")
    print()

    # Step 3: Propagate generated TLE over the evaluation span
    step_s = parse_step_to_seconds(args.step) if args.step else oem_step_s

    print(f"Step 2: Propagating generated TLE for {duration_s/3600:.2f}h at {step_s:.0f}s steps...")
    prop_records = run_propagate_tle(tle_text, duration_s, step_s)
    print(f"  Propagated {len(prop_records)} state vectors.")
    print()

    # Step 4: Evaluate differences
    print("Step 3: Evaluating position/velocity differences...")
    pos_errors, vel_errors, matched_count = evaluate_differences(oem_records, prop_records)
    print()

    duration_h = duration_s / 3600.0
    print_statistics(pos_errors, vel_errors, matched_count, len(oem_records), duration_h)


if __name__ == "__main__":
    main()
