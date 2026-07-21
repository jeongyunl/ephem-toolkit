#!/usr/bin/env python3
"""Evaluate detailed intermediate and final accuracy of fit_tle.

This script provides a comprehensive accuracy assessment of the TLE fitting
process in fit_tle_main.py, including:

  1. Input data summary (OEM file statistics)
  2. Estimation diagnostics (element estimation from OEM arc)
  3. Refinement diagnostics (state-match or Keplerian-match convergence)
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
    python3 oem_to_omm/evaluate_fit_tle.py --refinement keplerian
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.consts as consts
import common.oem as oem
import common.time_utils as time_utils
import common.tle as tle

from oem_to_omm import fit_common
from oem_to_omm import fit_tle_main as fit_tle
from oem_to_omm.fit_tle import estimation
from oem_to_omm.fit_tle import models
from oem_to_omm.fit_tle import orbital_mechanics
from oem_to_omm.fit_tle import refinement
from oem_to_omm.fit_tle import tle_builder

# ===================================================================
# Constants
# ===================================================================

SECONDS_PER_DAY: float = 86400.0
"""Number of seconds in one day."""

TWO_PI: float = 2.0 * math.pi
"""Two times pi (2π), used for angular conversions."""

MINUTES_PER_DAY: float = 1440.0
"""Number of minutes in one day."""


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
    tle_ephemeris = fit_tle.create_tle_ephemeris(
        line1_str, line2_str, object_name="EVAL"
    )

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

        results.append(
            {
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
            }
        )

    return results


def evaluate_estimation_methods(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
) -> dict:
    """Evaluate the estimation step with and without state-match initial guess.

    Compares the estimated elements from:
      - No state-match (averaged/blended values for mean elements)
      - State-match (osculating values as initial guess for refinement)

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        OEM state vectors.
    fit_span_s : float
        Fit span in seconds.

    Returns
    -------
    dict
        Dictionary with estimation diagnostics.
    """
    reference_timestamp = states[0][0]
    filtered_states = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    # Estimate without state-match (averaged/blended mean elements)
    estimated_no_match: models.Estimated = estimation.estimate_tle_fields(
        filtered_states, use_state_match=False
    )

    # Estimate with state-match (osculating values as initial guess)
    estimated_with_match: models.Estimated = estimation.estimate_tle_fields(
        filtered_states, use_state_match=True
    )

    # Compute RMS position error for each estimate using SGP4 propagation
    epoch_dt = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    time_offsets_s = np.array([ts - reference_timestamp for ts, _ in filtered_states])
    target_positions_m = np.array([sv[:3] for _, sv in filtered_states])

    def compute_rms_for_estimated(est: models.Estimated) -> float:
        """Compute RMS position error for an estimated element set."""
        # Convert estimated elements to mean elements array [a, e, i, omega, RAAN, M]
        n_rev_day = est.mean_motion_rev_per_day
        n_rad_min = n_rev_day * TWO_PI / MINUTES_PER_DAY
        a_er = (fit_tle._SGP4_KE / n_rad_min) ** (2.0 / 3.0)
        a_m = a_er * fit_tle._SGP4_R_E_KM * 1000.0

        mean_elements = np.array(
            [
                a_m,
                est.eccentricity,
                math.radians(est.inclination_deg),
                math.radians(est.arg_perigee_deg),
                math.radians(est.raan_deg),
                math.radians(est.mean_anomaly_deg),
            ]
        )

        try:
            residuals = fit_tle._compute_sgp4_residuals_from_mean_elements(
                mean_elements, epoch_year, epoch_day, time_offsets_s, target_positions_m
            )
            return float(np.sqrt(np.mean(residuals**2)))
        except Exception:
            return float("inf")

    rms_no_match = compute_rms_for_estimated(estimated_no_match)
    rms_with_match = compute_rms_for_estimated(estimated_with_match)

    return {
        "estimated_no_match": estimated_no_match,
        "estimated_with_match": estimated_with_match,
        "rms_no_match_m": rms_no_match,
        "rms_with_match_m": rms_with_match,
    }


def run_fit_all_refinement_methods(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
    mu_m3_s2: float,
    object_name: str = "LEO3",
    object_id: str = "2023-100G",
) -> dict[str, tuple[tle.Tle, fit_common.FitDiagnostics]]:
    """Run fit_tle with all refinement methods for comparison.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        OEM state vectors.
    fit_span_s : float
        Fit span in seconds.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    object_name : str
        Satellite name.
    object_id : str
        International designator.

    Returns
    -------
    dict[str, tuple[tle.Tle, fit_common.FitDiagnostics]]
        Results keyed by refinement method name.
    """
    results: dict[str, tuple[tle.Tle, fit_common.FitDiagnostics]] = {}

    for method in ["none", "keplerian", "cartesian"]:
        try:
            tle_obj, diagnostics = fit_tle.fit_tle(
                states,
                fit_span_s,
                method,
                mu_m3_s2,
                object_name=object_name,
                object_id=object_id,
            )
            results[method] = (tle_obj, diagnostics)
        except Exception as e:
            print(f"  WARNING: refinement method '{method}' failed: {e}")

    return results


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


def format_estimated_elements(est: models.Estimated) -> str:
    """Format estimated elements for display."""
    n_rev_day = est.mean_motion_rev_per_day
    n_rad_min = n_rev_day * TWO_PI / MINUTES_PER_DAY
    a_er = (fit_tle._SGP4_KE / n_rad_min) ** (2.0 / 3.0)
    a_km = a_er * fit_tle._SGP4_R_E_KM

    return (
        f"    a = {a_km:.6f} km (n = {n_rev_day:.10f} rev/day)\n"
        f"    e = {est.eccentricity:.10f}\n"
        f"    i = {est.inclination_deg:.6f} deg\n"
        f"    ω = {est.arg_perigee_deg:.6f} deg\n"
        f"    Ω = {est.raan_deg:.6f} deg\n"
        f"    M = {est.mean_anomaly_deg:.6f} deg"
    )


def main() -> None:
    """Run the detailed evaluation of fit_tle accuracy."""
    parser = argparse.ArgumentParser(
        description="Evaluate detailed intermediate and final accuracy of fit_tle"
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
        "--refinement",
        choices=["none", "cartesian", "keplerian", "all"],
        default="cartesian",
        metavar="<method>",
        dest="refinement_method",
        help=(
            "Refinement method: 'none', 'cartesian' (default), 'keplerian', "
            "or 'all' to compare all methods."
        ),
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
    print_section("EVALUATION OF fit_tle — DETAILED ACCURACY REPORT")

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
    # Section 2: Estimation — Initial Element Estimation
    # ===================================================================
    print_section("ESTIMATION: INITIAL ELEMENT ESTIMATION")

    print("  Computing element estimates (no state-match vs state-match)...")
    print()

    t_start = time.time()
    estimation_info = evaluate_estimation_methods(states, fit_span_s)
    t_estimation = time.time() - t_start

    print(f"  Estimation computation time: {t_estimation:.3f} s")
    print()

    print("  No state-match estimate (averaged/blended mean elements):")
    print(format_estimated_elements(estimation_info["estimated_no_match"]))
    print(f"    Arc-wide RMS: {estimation_info['rms_no_match_m']/1000:.6f} km")
    print()

    print("  State-match estimate (osculating values as initial guess):")
    print(format_estimated_elements(estimation_info["estimated_with_match"]))
    print(f"    Arc-wide RMS: {estimation_info['rms_with_match_m']/1000:.6f} km")
    print()

    est_no_match = estimation_info["estimated_no_match"]
    print(f"  Estimation metadata:")
    print(f"    Phase match count:  {est_no_match.phase_match_count}")
    print(f"    Phase match weight: {est_no_match.phase_match_weight:.4f}")
    print(
        f"    Mean motion dot:    {est_no_match.mean_motion_first_derivative:.12f} rev/day²"
    )
    print(
        f"    Dataset slope:      {est_no_match.dataset_slope_rev_per_day2:.6e} rev/day²"
    )

    # ===================================================================
    # Section 3: Refinement — TLE Fitting
    # ===================================================================
    print_section("REFINEMENT: TLE FITTING")

    object_name = oem_data.meta.object_name or "OBJECT"
    object_id = oem_data.meta.object_id or "UNKNOWN"

    if args.refinement_method == "all":
        print("  Running all refinement methods for comparison...")
        print()

        t_start = time.time()
        all_results = run_fit_all_refinement_methods(
            states,
            fit_span_s,
            args.mu_m3_s2,
            object_name=object_name,
            object_id=object_id,
        )
        t_refinement = time.time() - t_start

        print(f"  Total refinement time: {t_refinement:.3f} s")
        print()

        print(
            f"  {'Method':<12}  {'RMS (km)':>12}  "
            f"{'Iterations':>10}  {'Fit Method':>20}"
        )
        print(f"  {'─'*12}  {'─'*12}  {'─'*10}  {'─'*20}")

        for method_name, (tle_result, diag) in all_results.items():
            print(
                f"  {method_name:<12}  "
                f"{diag.rms_position_m/1000:12.6f}  "
                f"{diag.iterations:10d}  "
                f"{diag.fit_method:>20}"
            )

        # Use the best result for subsequent analysis
        best_method = min(all_results, key=lambda m: all_results[m][1].rms_position_m)
        tle_obj, diagnostics = all_results[best_method]
        print()
        print(
            f"  ► Best method: {best_method} (RMS = {diagnostics.rms_position_m/1000:.6f} km)"
        )

    else:
        print(f"  Running refinement method: {args.refinement_method}")
        print()

        t_start = time.time()
        tle_obj, diagnostics = fit_tle.fit_tle(
            states,
            fit_span_s,
            args.refinement_method,
            args.mu_m3_s2,
            object_name=object_name,
            object_id=object_id,
        )
        t_refinement = time.time() - t_start

        print(f"  Refinement computation time: {t_refinement:.3f} s")

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
    print(f"    RMS position error: {diagnostics.rms_position_m/1000:.6f} km")
    print(f"    Iterations:         {diagnostics.iterations}")
    print(f"    Records used:       {diagnostics.n_records}")
    print(
        f"    Arc span:           {diagnostics.span_s:.1f} s ({diagnostics.span_s/3600:.2f} h)"
    )
    print(f"    Fit method:         {diagnostics.fit_method}")
    if diagnostics.epoch_pos_delta_m is not None:
        print(f"    Epoch |Δr|:         {diagnostics.epoch_pos_delta_m/1000:.6f} km")
    if diagnostics.epoch_vel_delta_m_s is not None:
        print(
            f"    Epoch |Δv|:         {diagnostics.epoch_vel_delta_m_s/1000:.9f} km/s"
        )

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
    print(
        f"    Mean motion dot:    {tle_obj.mean_motion_first_derivative:.12f} rev/day²"
    )

    # ===================================================================
    # Section 5: Per-Epoch Error Analysis
    # ===================================================================
    print_section("PER-EPOCH ERROR ANALYSIS (TLE vs OEM)")

    per_epoch_errors = compute_per_epoch_errors(tle_obj, states, fit_span_s)

    if per_epoch_errors:
        # Print table header
        print(
            f"  {'t (min)':>8}  {'|Δr| (km)':>12}  "
            f"{'|Δv| (km/s)':>12}  {'Δx (km)':>12}  {'Δy (km)':>12}  {'Δz (km)':>12}"
        )
        print(f"  {'─'*8}  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*12}")

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
            print(
                f"  {rec['elapsed_min']:8.1f}  "
                f"{rec['pos_err_m']/1000:12.6f}  "
                f"{rec['vel_err_m_s']/1000:12.9f}  "
                f"{rec['dx_m']/1000:12.6f}  "
                f"{rec['dy_m']/1000:12.6f}  "
                f"{rec['dz_m']/1000:12.6f}"
            )

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
        print(
            f"  {'Time bin':>14}  {'RMS |Δr| (km)':>14}  {'Max |Δr| (km)':>14}  "
            f"{'RMS |Δv| (km/s)':>16}  {'N pts':>6}"
        )
        print(f"  {'─'*14}  {'─'*14}  {'─'*14}  {'─'*16}  {'─'*6}")

        for bin_idx in range(n_bins):
            t_start_min = bin_idx * bin_size_min
            t_end_min = (bin_idx + 1) * bin_size_min

            bin_records = [
                r
                for r in per_epoch_errors
                if t_start_min <= r["elapsed_min"] < t_end_min
            ]

            if not bin_records:
                continue

            pos_errs = [r["pos_err_m"] for r in bin_records]
            vel_errs = [r["vel_err_m_s"] for r in bin_records]

            rms_pos = math.sqrt(sum(e**2 for e in pos_errs) / len(pos_errs))
            max_pos = max(pos_errs)
            rms_vel = math.sqrt(sum(e**2 for e in vel_errs) / len(vel_errs))

            print(
                f"  {t_start_min:5.0f}-{t_end_min:5.0f} min  "
                f"{rms_pos/1000:14.6f}  "
                f"{max_pos/1000:14.6f}  "
                f"{rms_vel/1000:16.9f}  "
                f"{len(bin_records):6d}"
            )

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
        print(f"    RMS:     {rms_pos/1000:12.6f} km")
        print(f"    Mean:    {mean_pos/1000:12.6f} km")
        print(f"    Median:  {median_pos/1000:12.6f} km")
        print(f"    Min:     {min_pos/1000:12.6f} km")
        print(f"    Max:     {max_pos/1000:12.6f} km")
        print()
        print(f"  Velocity error |Δv|:")
        print(f"    RMS:     {rms_vel/1000:12.9f} km/s")
        print(f"    Mean:    {mean_vel/1000:12.9f} km/s")
        print(f"    Median:  {median_vel/1000:12.9f} km/s")
        print(f"    Min:     {min_vel/1000:12.9f} km/s")
        print(f"    Max:     {max_vel/1000:12.9f} km/s")
        print()

        # Epoch accuracy
        epoch_rec = per_epoch_errors[0]
        print(f"  Epoch accuracy (t=0):")
        print(f"    |Δr| = {epoch_rec['pos_err_m']/1000:.6f} km")
        print(f"    |Δv| = {epoch_rec['vel_err_m_s']/1000:.9f} km/s")
        print()

        # End-of-arc accuracy
        end_rec = per_epoch_errors[-1]
        print(f"  End-of-arc accuracy (t={end_rec['elapsed_min']:.1f} min):")
        print(f"    |Δr| = {end_rec['pos_err_m']/1000:.6f} km")
        print(f"    |Δv| = {end_rec['vel_err_m_s']/1000:.9f} km/s")
        print()

        # Error at key time points
        print(f"  Error at key time points:")
        key_times_min = [0, 30, 60, 90, 120, 180, 240, 300, 360]
        print(f"    {'t (min)':>8}  {'|Δr| (km)':>12}  {'|Δv| (km/s)':>12}")
        print(f"    {'���'*8}  {'─'*12}  {'─'*12}")

        for t_min in key_times_min:
            if t_min * 60.0 > fit_span_s:
                break
            # Find closest record
            closest = min(per_epoch_errors, key=lambda r: abs(r["elapsed_min"] - t_min))
            if abs(closest["elapsed_min"] - t_min) < 5.0:  # within 5 min
                print(
                    f"    {closest['elapsed_min']:8.1f}  "
                    f"{closest['pos_err_m']/1000:12.6f}  "
                    f"{closest['vel_err_m_s']/1000:12.9f}"
                )

    # ===================================================================
    # Section 8: Timing Summary
    # ===================================================================
    print_section("TIMING SUMMARY")
    print(f"  Estimation (initial guess):  {t_estimation:.3f} s")
    print(f"  Refinement (fit):            {t_refinement:.3f} s")
    print(f"  Total fit time:              {t_estimation + t_refinement:.3f} s")
    print()

    print_separator()
    print("  EVALUATION COMPLETE")
    print_separator()


if __name__ == "__main__":
    main()
