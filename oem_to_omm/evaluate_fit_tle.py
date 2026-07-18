#!/usr/bin/env python3
"""Evaluate detailed intermediate and final accuracy of fit_tle.py.

This script provides a comprehensive accuracy assessment of the TLE fitting
process in fit_tle.py, including:

  1. Input data summary (OEM file statistics)
  2. Phase 1 diagnostics (statistical vs single-state initial guess)
  3. Phase 2 diagnostics (Gauss-Newton convergence history)
  4. Final TLE accuracy (position/velocity errors at each OEM epoch)
  5. Error growth analysis (how accuracy degrades over time)
  6. Summary statistics (RMS, max, mean errors)

Usage:
    python3 oem_to_omm/evaluate_fit_tle.py [--fit-span <hours>] [<oem_file>]

    Default input: oem_to_omm/leo3_6h.oem
    Default fit span: 6 hours (full file)

Examples:
    python3 oem_to_omm/evaluate_fit_tle.py
    python3 oem_to_omm/evaluate_fit_tle.py --fit-span 2.0
    python3 oem_to_omm/evaluate_fit_tle.py oem_to_omm/leo3_3h.oem
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common.consts as consts
import common.oem as oem
import common.time_utils as time_utils
import common.tle as tle

import fit_common
import fit_tle


# ===================================================================
# Constants
# ===================================================================

SECONDS_PER_DAY: float = 86400.0
TWO_PI: float = 2.0 * math.pi
MINUTES_PER_DAY: float = 1440.0


# ===================================================================
# Evaluation helpers
# ===================================================================


def compute_per_epoch_errors(
    tle_obj: tle.Tle,
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
) -> list[dict]:
    """Compute position and velocity errors at each OEM epoch.

    Parameters
    ----------
    tle_obj : tle.Tle
        Fitted TLE object.
    states : list[tuple[float, np.ndarray]]
        OEM state vectors (POSIX timestamp, [x,y,z,vx,vy,vz] in m, m/s).
    fit_span_s : float
        Maximum time span to evaluate (seconds).

    Returns
    -------
    list[dict]
        Per-epoch error records with keys: elapsed_s, elapsed_min,
        pos_err_m, vel_err_m_s, dx_m, dy_m, dz_m, dvx_m_s, dvy_m_s, dvz_m_s.
    """
    reference_timestamp: float = states[0][0]

    # Filter to fit span
    filtered_states = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    if not filtered_states:
        return []

    # Create SGP4 ephemeris from TLE
    line1_str, line2_str = tle.format_tle_strings(tle_obj)
    tle_ephemeris = fit_tle.create_tle_ephemeris(line1_str, line2_str, object_name="EVAL")

    results: list[dict] = []

    for ts, sv in filtered_states:
        elapsed_s = ts - reference_timestamp

        # Propagate TLE to this epoch
        predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
            tle_ephemeris.tle.reference_epoch + elapsed_s
        )

        # Compute differences
        pos_diff = sv[:3] - predicted_state[:3]
        vel_diff = sv[3:6] - predicted_state[3:6]

        pos_err = float(np.linalg.norm(pos_diff))
        vel_err = float(np.linalg.norm(vel_diff))

        results.append({
            "elapsed_s": elapsed_s,
            "elapsed_min": elapsed_s / 60.0,
            "pos_err_m": pos_err,
            "vel_err_m_s": vel_err,
            "dx_m": float(pos_diff[0]),
            "dy_m": float(pos_diff[1]),
            "dz_m": float(pos_diff[2]),
            "dvx_m_s": float(vel_diff[0]),
            "dvy_m_s": float(vel_diff[1]),
            "dvz_m_s": float(vel_diff[2]),
        })

    return results


def evaluate_initial_guess(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
    mu_m3_s2: float,
) -> dict:
    """Evaluate both Phase 1 initial guess candidates.

    Returns RMS position errors for:
      - Statistical estimate (median/circular-mean of all states)
      - Single-state Gauss-Newton estimate (from first state only)

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        OEM state vectors.
    fit_span_s : float
        Fit span in seconds.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    dict
        Dictionary with keys: statistical_rms_m, single_state_rms_m,
        chosen_method, statistical_elements, single_state_elements.
    """
    reference_timestamp = states[0][0]
    filtered_states = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    first_state = filtered_states[0][1]

    # Get epoch
    epoch_dt = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    # Collect time offsets and target positions
    time_offsets_s = np.array([ts - reference_timestamp for ts, _ in filtered_states])
    target_positions_m = np.array([sv[:3] for _, sv in filtered_states])

    # Phase 1a: Statistical estimation
    statistical_elements = fit_tle._estimate_mean_elements_statistically(
        filtered_states, reference_timestamp, mu_m3_s2
    )

    # Phase 1b: Single-state Gauss-Newton
    single_state_elements = fit_tle.cartesian_to_tle_mean_elements(
        first_state, reference_timestamp, mu_m3_s2=mu_m3_s2,
        position_tolerance_m=15.0, max_iterations=50,
    )

    # Evaluate both against full arc
    try:
        residuals_stat = fit_tle._compute_sgp4_residuals_from_mean_elements(
            statistical_elements, epoch_year, epoch_day, time_offsets_s, target_positions_m
        )
        rms_stat = float(np.sqrt(np.mean(residuals_stat ** 2)))
    except Exception:
        rms_stat = float("inf")

    try:
        residuals_single = fit_tle._compute_sgp4_residuals_from_mean_elements(
            single_state_elements, epoch_year, epoch_day, time_offsets_s, target_positions_m
        )
        rms_single = float(np.sqrt(np.mean(residuals_single ** 2)))
    except Exception:
        rms_single = float("inf")

    chosen = "statistical" if rms_stat < rms_single else "single_state"

    return {
        "statistical_rms_m": rms_stat,
        "single_state_rms_m": rms_single,
        "chosen_method": chosen,
        "statistical_elements": statistical_elements,
        "single_state_elements": single_state_elements,
    }


def run_fit_with_convergence_history(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
    mu_m3_s2: float,
    max_iterations: int = 200,
) -> tuple[tle.Tle, fit_common.FitDiagnostics, list[dict]]:
    """Run fit_tle with instrumented convergence tracking.

    This re-implements the Phase 2 Gauss-Newton loop to capture per-iteration
    RMS values, while still using the same algorithm as fit_tle.fit_tle().

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        OEM state vectors.
    fit_span_s : float
        Fit span in seconds.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    max_iterations : int
        Maximum Gauss-Newton iterations.

    Returns
    -------
    tuple[tle.Tle, fit_common.FitDiagnostics, list[dict]]
        Fitted TLE, diagnostics, and convergence history.
    """
    reference_timestamp = states[0][0]
    filtered_states = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    first_state = filtered_states[0][1]
    epoch_dt = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    time_offsets_s = np.array([ts - reference_timestamp for ts, _ in filtered_states])
    target_positions_m = np.array([sv[:3] for _, sv in filtered_states])

    # Phase 1: Get initial guess (same as fit_tle)
    statistical_elements = fit_tle._estimate_mean_elements_statistically(
        filtered_states, reference_timestamp, mu_m3_s2
    )
    initial_mean_elements = fit_tle.cartesian_to_tle_mean_elements(
        first_state, reference_timestamp, mu_m3_s2=mu_m3_s2,
        position_tolerance_m=15.0, max_iterations=50,
    )

    try:
        rms_statistical = float(np.sqrt(np.mean(
            fit_tle._compute_sgp4_residuals_from_mean_elements(
                statistical_elements, epoch_year, epoch_day, time_offsets_s, target_positions_m
            ) ** 2
        )))
    except Exception:
        rms_statistical = float("inf")

    try:
        rms_single_state = float(np.sqrt(np.mean(
            fit_tle._compute_sgp4_residuals_from_mean_elements(
                initial_mean_elements, epoch_year, epoch_day, time_offsets_s, target_positions_m
            ) ** 2
        )))
    except Exception:
        rms_single_state = float("inf")

    if rms_statistical < rms_single_state:
        x = statistical_elements.copy()
    else:
        x = initial_mean_elements.copy()

    # Phase 2: Gauss-Newton with convergence tracking
    h = np.array([500.0, 1e-6, 1e-5, 1e-5, 1e-5, 1e-5])

    best_x = x.copy()
    best_rms = float("inf")
    prev_rms = float("inf")
    final_iter = 0
    convergence_history: list[dict] = []

    for iteration in range(max_iterations):
        try:
            residuals = fit_tle._compute_sgp4_residuals_from_mean_elements(
                x, epoch_year, epoch_day, time_offsets_s, target_positions_m
            )
        except Exception:
            break

        rms = float(np.sqrt(np.mean(residuals ** 2)))
        max_pos_err = float(np.max(np.sqrt(
            residuals[0::3]**2 + residuals[1::3]**2 + residuals[2::3]**2
        )))

        convergence_history.append({
            "iteration": iteration,
            "rms_m": rms,
            "max_pos_err_m": max_pos_err,
            "a_m": float(x[0]),
            "e": float(x[1]),
            "i_deg": math.degrees(float(x[2])),
        })

        if rms < best_rms:
            best_rms = rms
            best_x = x.copy()

        # Convergence check
        if iteration > 0:
            rel_change = abs(prev_rms - rms) / max(rms, 1.0)
            if rel_change < 1.0e-8 or (rms < 100.0 and abs(prev_rms - rms) < 1.0):
                final_iter = iteration
                break
        prev_rms = rms
        final_iter = iteration

        # Build Jacobian
        n_residuals = len(residuals)
        jacobian = np.zeros((n_residuals, 6))
        for j in range(6):
            x_plus, x_minus = x.copy(), x.copy()
            x_plus[j] += h[j]
            x_minus[j] -= h[j]
            if j == 1:
                x_plus[j] = min(0.9, max(1e-7, x_plus[j]))
                x_minus[j] = min(0.9, max(1e-7, x_minus[j]))
            try:
                res_plus = fit_tle._compute_sgp4_residuals_from_mean_elements(
                    x_plus, epoch_year, epoch_day, time_offsets_s, target_positions_m
                )
                res_minus = fit_tle._compute_sgp4_residuals_from_mean_elements(
                    x_minus, epoch_year, epoch_day, time_offsets_s, target_positions_m
                )
                jacobian[:, j] = (res_plus - res_minus) / (2.0 * h[j])
            except Exception:
                jacobian[:, j] = 0.0

        # Solve normal equations
        try:
            jt_j = jacobian.T @ jacobian + 1e-8 * np.eye(6)
            jt_r = jacobian.T @ residuals
            dx = np.linalg.solve(jt_j, jt_r)
        except np.linalg.LinAlgError:
            break

        max_step = np.array([10000.0, 0.05, 0.05, 0.5, 0.5, 1.0])
        dx = np.clip(dx, -max_step, max_step)

        # Line search
        alpha = 1.0
        improved = False
        for _ in range(15):
            x_new = x + alpha * dx
            x_new[0] = max(6.4e6, x_new[0])
            x_new[1] = max(1e-7, min(0.9, x_new[1]))
            x_new[2] = max(0.0, min(math.pi, x_new[2]))
            for k in [3, 4, 5]:
                x_new[k] = x_new[k] % TWO_PI
                if x_new[k] < 0:
                    x_new[k] += TWO_PI
            try:
                trial_residuals = fit_tle._compute_sgp4_residuals_from_mean_elements(
                    x_new, epoch_year, epoch_day, time_offsets_s, target_positions_m
                )
                trial_rms = float(np.sqrt(np.mean(trial_residuals ** 2)))
                if trial_rms < rms:
                    x = x_new
                    improved = True
                    break
            except Exception:
                pass
            alpha *= 0.5

        if not improved and iteration > 10:
            break

    # Now run the actual fit_tle to get the final TLE object
    tle_obj, diagnostics = fit_tle.fit_tle(
        states, fit_span_s, mu_m3_s2,
        max_iterations=max_iterations,
        object_name="LEO3",
        object_id="2023-100G",
    )

    return tle_obj, diagnostics, convergence_history


# ===================================================================
# Reporting
# ===================================================================


def print_separator(char: str = "=", width: int = 72) -> None:
    """Print a separator line."""
    print(char * width)


def print_section(title: str) -> None:
    """Print a section header."""
    print()
    print_separator()
    print(f"  {title}")
    print_separator()
    print()


def format_elements(elements: np.ndarray) -> str:
    """Format mean elements for display."""
    a_km = elements[0] / 1000.0
    e = elements[1]
    i_deg = math.degrees(elements[2])
    omega_deg = math.degrees(elements[3])
    raan_deg = math.degrees(elements[4])
    M_deg = math.degrees(elements[5])
    return (
        f"    a = {a_km:.6f} km\n"
        f"    e = {e:.10f}\n"
        f"    i = {i_deg:.6f} deg\n"
        f"    ω = {omega_deg:.6f} deg\n"
        f"    Ω = {raan_deg:.6f} deg\n"
        f"    M = {M_deg:.6f} deg"
    )


def main() -> None:
    """Run the detailed evaluation of fit_tle.py accuracy."""
    parser = argparse.ArgumentParser(
        description="Evaluate detailed intermediate and final accuracy of fit_tle.py"
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        default=str(Path(__file__).parent / "leo3_6h.oem"),
        help="Path to input CCSDS OEM file (default: oem_to_omm/leo3_6h.oem)",
    )
    parser.add_argument(
        "--fit-span",
        type=float,
        default=None,
        metavar="<hours>",
        dest="fit_span_hours",
        help="Fit span in hours (default: use full OEM span).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=200,
        metavar="<N>",
        dest="max_iterations",
        help="Maximum Gauss-Newton iterations (default: 200).",
    )
    parser.add_argument(
        "--mu",
        type=float,
        default=consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        metavar="<value>",
        dest="mu_m3_s2",
        help="Gravitational parameter (m³/s²).",
    )

    args = parser.parse_args()

    oem_path = Path(args.oem_file)
    if not oem_path.exists():
        print(f"ERROR: OEM file not found: {oem_path}", file=sys.stderr)
        sys.exit(1)

    # ===================================================================
    # Section 1: Input Data Summary
    # ===================================================================
    print_section("EVALUATION OF fit_tle.py — DETAILED ACCURACY REPORT")

    print(f"  Input file:     {oem_path.name}")
    print(f"  Full path:      {oem_path.resolve()}")

    # Read OEM
    oem_data = oem.CcsdsOem.read(oem_path)
    states = oem_data.states

    if len(states) < 2:
        print("ERROR: OEM file has fewer than 2 state vectors.", file=sys.stderr)
        sys.exit(1)

    reference_timestamp = states[0][0]
    total_span_s = states[-1][0] - reference_timestamp
    step_s = states[1][0] - states[0][0] if len(states) > 1 else 0.0

    # Determine fit span
    if args.fit_span_hours is not None:
        fit_span_s = args.fit_span_hours * 3600.0
    else:
        fit_span_s = total_span_s

    filtered_states = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    epoch_dt = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(states[-1][0], tz=timezone.utc)

    print(f"  Object name:    {oem_data.meta.object_name}")
    print(f"  Object ID:      {oem_data.meta.object_id}")
    print(f"  Reference frame:{oem_data.meta.ref_frame}")
    print(f"  Epoch (start):  {time_utils.datetime_to_iso8601(epoch_dt)}")
    print(f"  End time:       {time_utils.datetime_to_iso8601(end_dt)}")
    print(f"  Total span:     {total_span_s:.1f} s ({total_span_s/3600:.2f} h)")
    print(f"  Step size:      {step_s:.1f} s ({step_s/60:.1f} min)")
    print(f"  Total records:  {len(states)}")
    print(f"  Fit span:       {fit_span_s:.1f} s ({fit_span_s/3600:.2f} h)")
    print(f"  Records in fit: {len(filtered_states)}")
    print()

    # Initial state info
    first_state = states[0][1]
    r0 = float(np.linalg.norm(first_state[:3]))
    v0 = float(np.linalg.norm(first_state[3:6]))
    alt_km = (r0 - consts.EARTH_EQUATORIAL_RADIUS_M) / 1000.0
    print(f"  Initial state:")
    print(f"    |r₀| = {r0/1000:.6f} km  (altitude ≈ {alt_km:.1f} km)")
    print(f"    |v₀| = {v0/1000:.6f} km/s")

    # ===================================================================
    # Section 2: Phase 1 — Initial Guess Evaluation
    # ===================================================================
    print_section("PHASE 1: INITIAL GUESS EVALUATION")

    print("  Computing statistical estimate (median/circular-mean of all states)...")
    print("  Computing single-state Gauss-Newton estimate (from epoch state)...")
    print()

    t_start = time.time()
    guess_info = evaluate_initial_guess(states, fit_span_s, args.mu_m3_s2)
    t_phase1 = time.time() - t_start

    print(f"  Phase 1 computation time: {t_phase1:.3f} s")
    print()

    print("  Statistical estimate (all-state median + J2 back-propagation):")
    print(format_elements(guess_info["statistical_elements"]))
    print(f"    Arc-wide RMS: {guess_info['statistical_rms_m']:.3f} m "
          f"({guess_info['statistical_rms_m']/1000:.6f} km)")
    print()

    print("  Single-state estimate (Gauss-Newton from epoch state):")
    print(format_elements(guess_info["single_state_elements"]))
    print(f"    Arc-wide RMS: {guess_info['single_state_rms_m']:.3f} m "
          f"({guess_info['single_state_rms_m']/1000:.6f} km)")
    print()

    print(f"  ► Chosen initial guess: {guess_info['chosen_method']}")
    improvement_factor = max(guess_info['statistical_rms_m'], guess_info['single_state_rms_m']) / \
                         min(guess_info['statistical_rms_m'], guess_info['single_state_rms_m'])
    print(f"    (better by factor {improvement_factor:.2f}x)")

    # ===================================================================
    # Section 3: Phase 2 — Gauss-Newton Convergence
    # ===================================================================
    print_section("PHASE 2: GAUSS-NEWTON CONVERGENCE HISTORY")

    print("  Running Gauss-Newton refinement with convergence tracking...")
    print()

    t_start = time.time()
    tle_obj, diagnostics, convergence_history = run_fit_with_convergence_history(
        states, fit_span_s, args.mu_m3_s2, max_iterations=args.max_iterations
    )
    t_phase2 = time.time() - t_start

    print(f"  Phase 2 computation time: {t_phase2:.3f} s")
    print(f"  Total iterations: {len(convergence_history)}")
    print()

    if convergence_history:
        # Print convergence table (selected iterations)
        print(f"  {'Iter':>5}  {'RMS (m)':>12}  {'Max Err (m)':>12}  "
              f"{'a (km)':>12}  {'e':>12}  {'i (deg)':>10}")
        print(f"  {'─'*5}  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*10}")

        # Show first 5, then every 10th, then last 5
        n_hist = len(convergence_history)
        indices_to_show = set()
        # First 5
        for i in range(min(5, n_hist)):
            indices_to_show.add(i)
        # Every 10th
        for i in range(0, n_hist, 10):
            indices_to_show.add(i)
        # Last 5
        for i in range(max(0, n_hist - 5), n_hist):
            indices_to_show.add(i)

        prev_idx = -1
        for idx in sorted(indices_to_show):
            if prev_idx >= 0 and idx - prev_idx > 1:
                print(f"  {'...':>5}")
            rec = convergence_history[idx]
            print(f"  {rec['iteration']:5d}  "
                  f"{rec['rms_m']:12.3f}  "
                  f"{rec['max_pos_err_m']:12.3f}  "
                  f"{rec['a_m']/1000:12.3f}  "
                  f"{rec['e']:12.10f}  "
                  f"{rec['i_deg']:10.6f}")
            prev_idx = idx

        print()
        # Convergence summary
        initial_rms = convergence_history[0]["rms_m"]
        final_rms = convergence_history[-1]["rms_m"]
        print(f"  Convergence summary:")
        print(f"    Initial RMS:  {initial_rms:.3f} m ({initial_rms/1000:.6f} km)")
        print(f"    Final RMS:    {final_rms:.3f} m ({final_rms/1000:.6f} km)")
        if initial_rms > 0:
            print(f"    Improvement:  {initial_rms/max(final_rms, 1e-10):.1f}x")

    # ===================================================================
    # Section 4: Final TLE Output
    # ===================================================================
    print_section("FINAL FITTED TLE")

    line1_str, line2_str = tle.format_tle_strings(tle_obj)
    print(f"  {tle_obj.name}")
    print(f"  {line1_str}")
    print(f"  {line2_str}")
    print()
    print(f"  Fit diagnostics:")
    print(f"    RMS position error: {diagnostics.rms_position_m:.3f} m "
          f"({diagnostics.rms_position_m/1000:.6f} km)")
    print(f"    Iterations:         {diagnostics.iterations}")
    print(f"    Records used:       {diagnostics.n_records}")
    print(f"    Arc span:           {diagnostics.span_s:.1f} s ({diagnostics.span_s/3600:.2f} h)")
    print(f"    Fit method:         {diagnostics.fit_method}")

    # Derived orbital parameters
    n_rev_day = tle_obj.mean_motion_rev_per_day
    n_rad_min = n_rev_day * TWO_PI / MINUTES_PER_DAY
    a_er = (fit_tle._SGP4_KE / n_rad_min) ** (2.0 / 3.0)
    a_km = a_er * fit_tle._SGP4_R_E_KM
    period_s = TWO_PI / (n_rev_day * TWO_PI / SECONDS_PER_DAY)
    alt_km_tle = a_km - consts.EARTH_EQUATORIAL_RADIUS_M / 1000.0

    print()
    print(f"  Orbital elements:")
    print(f"    Semi-major axis:    {a_km:.6f} km (altitude ≈ {alt_km_tle:.1f} km)")
    print(f"    Eccentricity:       {tle_obj.eccentricity:.10f}")
    print(f"    Inclination:        {tle_obj.inclination_deg:.6f} deg")
    print(f"    RAAN:               {tle_obj.raan_deg:.6f} deg")
    print(f"    Arg of perigee:     {tle_obj.arg_perigee_deg:.6f} deg")
    print(f"    Mean anomaly:       {tle_obj.mean_anomaly_deg:.6f} deg")
    print(f"    Mean motion:        {n_rev_day:.10f} rev/day")
    print(f"    Orbital period:     {period_s:.3f} s ({period_s/60:.2f} min)")
    print(f"    BSTAR:              {tle_obj.bstar}")
    print(f"    Mean motion dot:    {tle_obj.mean_motion_first_derivative:.12f} rev/day²")

    # ===================================================================
    # Section 5: Per-Epoch Error Analysis
    # ===================================================================
    print_section("PER-EPOCH ERROR ANALYSIS (TLE vs OEM)")

    per_epoch_errors = compute_per_epoch_errors(tle_obj, states, fit_span_s)

    if per_epoch_errors:
        # Print table header
        print(f"  {'t (min)':>8}  {'|Δr| (m)':>10}  {'|Δr| (km)':>10}  "
              f"{'|Δv| (m/s)':>10}  {'Δx (m)':>10}  {'Δy (m)':>10}  {'Δz (m)':>10}")
        print(f"  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}")

        # Show every Nth record to keep output manageable
        n_records = len(per_epoch_errors)
        if n_records <= 40:
            step = 1
        elif n_records <= 100:
            step = 3
        else:
            step = max(1, n_records // 40)

        indices_to_show = list(range(0, n_records, step))
        if (n_records - 1) not in indices_to_show:
            indices_to_show.append(n_records - 1)

        for idx in indices_to_show:
            rec = per_epoch_errors[idx]
            print(f"  {rec['elapsed_min']:8.1f}  "
                  f"{rec['pos_err_m']:10.3f}  "
                  f"{rec['pos_err_m']/1000:10.6f}  "
                  f"{rec['vel_err_m_s']:10.6f}  "
                  f"{rec['dx_m']:10.3f}  "
                  f"{rec['dy_m']:10.3f}  "
                  f"{rec['dz_m']:10.3f}")

        # ===================================================================
        # Section 6: Error Growth Analysis
        # ===================================================================
        print_section("ERROR GROWTH ANALYSIS")

        # Bin errors by time intervals (every 30 minutes)
        bin_size_min = 30.0
        max_time_min = per_epoch_errors[-1]["elapsed_min"]
        n_bins = max(1, int(math.ceil(max_time_min / bin_size_min)))

        print(f"  Error statistics in {bin_size_min:.0f}-minute bins:")
        print()
        print(f"  {'Time bin':>14}  {'RMS |Δr| (m)':>12}  {'Max |Δr| (m)':>12}  "
              f"{'RMS |Δv| (m/s)':>14}  {'N pts':>6}")
        print(f"  {'─'*14}  {'─'*12}  {'─'*12}  {'─'*14}  {'─'*6}")

        for b in range(n_bins):
            t_start_min = b * bin_size_min
            t_end_min = (b + 1) * bin_size_min

            bin_records = [
                r for r in per_epoch_errors
                if t_start_min <= r["elapsed_min"] < t_end_min
            ]

            if not bin_records:
                continue

            pos_errs = [r["pos_err_m"] for r in bin_records]
            vel_errs = [r["vel_err_m_s"] for r in bin_records]

            rms_pos = math.sqrt(sum(e**2 for e in pos_errs) / len(pos_errs))
            max_pos = max(pos_errs)
            rms_vel = math.sqrt(sum(e**2 for e in vel_errs) / len(vel_errs))

            print(f"  {t_start_min:5.0f}-{t_end_min:5.0f} min  "
                  f"{rms_pos:12.3f}  "
                  f"{max_pos:12.3f}  "
                  f"{rms_vel:14.6f}  "
                  f"{len(bin_records):6d}")

        # ===================================================================
        # Section 7: Summary Statistics
        # ===================================================================
        print_section("SUMMARY STATISTICS")

        pos_errs_all = [r["pos_err_m"] for r in per_epoch_errors]
        vel_errs_all = [r["vel_err_m_s"] for r in per_epoch_errors]

        rms_pos = math.sqrt(sum(e**2 for e in pos_errs_all) / len(pos_errs_all))
        mean_pos = sum(pos_errs_all) / len(pos_errs_all)
        max_pos = max(pos_errs_all)
        min_pos = min(pos_errs_all)
        median_pos = float(np.median(pos_errs_all))

        rms_vel = math.sqrt(sum(e**2 for e in vel_errs_all) / len(vel_errs_all))
        mean_vel = sum(vel_errs_all) / len(vel_errs_all)
        max_vel = max(vel_errs_all)
        min_vel = min(vel_errs_all)
        median_vel = float(np.median(vel_errs_all))

        print(f"  Position error |Δr|:")
        print(f"    RMS:     {rms_pos:12.3f} m   ({rms_pos/1000:.6f} km)")
        print(f"    Mean:    {mean_pos:12.3f} m   ({mean_pos/1000:.6f} km)")
        print(f"    Median:  {median_pos:12.3f} m   ({median_pos/1000:.6f} km)")
        print(f"    Min:     {min_pos:12.3f} m   ({min_pos/1000:.6f} km)")
        print(f"    Max:     {max_pos:12.3f} m   ({max_pos/1000:.6f} km)")
        print()
        print(f"  Velocity error |Δv|:")
        print(f"    RMS:     {rms_vel:12.6f} m/s ({rms_vel/1000:.9f} km/s)")
        print(f"    Mean:    {mean_vel:12.6f} m/s ({mean_vel/1000:.9f} km/s)")
        print(f"    Median:  {median_vel:12.6f} m/s ({median_vel/1000:.9f} km/s)")
        print(f"    Min:     {min_vel:12.6f} m/s ({min_vel/1000:.9f} km/s)")
        print(f"    Max:     {max_vel:12.6f} m/s ({max_vel/1000:.9f} km/s)")
        print()

        # Epoch accuracy
        epoch_rec = per_epoch_errors[0]
        print(f"  Epoch accuracy (t=0):")
        print(f"    |Δr| = {epoch_rec['pos_err_m']:.3f} m")
        print(f"    |Δv| = {epoch_rec['vel_err_m_s']:.6f} m/s")
        print()

        # End-of-arc accuracy
        end_rec = per_epoch_errors[-1]
        print(f"  End-of-arc accuracy (t={end_rec['elapsed_min']:.1f} min):")
        print(f"    |Δr| = {end_rec['pos_err_m']:.3f} m")
        print(f"    |Δv| = {end_rec['vel_err_m_s']:.6f} m/s")
        print()

        # Error at key time points
        print(f"  Error at key time points:")
        key_times_min = [0, 30, 60, 90, 120, 180, 240, 300, 360]
        print(f"    {'t (min)':>8}  {'|Δr| (m)':>10}  {'|Δr| (km)':>10}  {'|Δv| (m/s)':>10}")
        print(f"    {'─'*8}  {'─'*10}  {'─'*10}  {'─'*10}")

        for t_min in key_times_min:
            if t_min * 60.0 > fit_span_s:
                break
            # Find closest record
            closest = min(per_epoch_errors, key=lambda r: abs(r["elapsed_min"] - t_min))
            if abs(closest["elapsed_min"] - t_min) < 5.0:  # within 5 min
                print(f"    {closest['elapsed_min']:8.1f}  "
                      f"{closest['pos_err_m']:10.3f}  "
                      f"{closest['pos_err_m']/1000:10.6f}  "
                      f"{closest['vel_err_m_s']:10.6f}")

    # ===================================================================
    # Section 8: Timing Summary
    # ===================================================================
    print_section("TIMING SUMMARY")
    print(f"  Phase 1 (initial guess):     {t_phase1:.3f} s")
    print(f"  Phase 2 (Gauss-Newton):      {t_phase2:.3f} s")
    print(f"  Total fit time:              {t_phase1 + t_phase2:.3f} s")
    print()

    print_separator()
    print("  EVALUATION COMPLETE")
    print_separator()


if __name__ == "__main__":
    main()
