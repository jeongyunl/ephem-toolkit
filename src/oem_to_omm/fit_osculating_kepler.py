"""Fit osculating Keplerian elements to OEM arcs using two-body propagation.

This module provides functions to fit osculating Keplerian orbital elements to
Orbit Ephemeris Message (OEM) state vectors using a Gauss-Newton least-squares
approach with two-body Kepler propagation. The fitting enforces that the epoch
position matches the first OEM position exactly while optimizing the epoch
velocity to minimize position residuals across the arc.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

import common.consts as consts
import common.kepler as kepler
import common.time_utils as time_utils
from . import fit_common


def _compute_kepler_residuals_from_epoch_state(
    epoch_state_m_m_s: np.ndarray,
    time_offsets_s: np.ndarray,
    target_positions_m: np.ndarray,
    mu_m3_s2: float,
) -> np.ndarray:
    """Compute position residuals between Kepler-propagated states and OEM targets.

    This function enforces *internal consistency* between the epoch Cartesian
    state and the Keplerian elements used for propagation by recomputing the
    Keplerian elements from the epoch state on every call.

    Parameters
    ----------
    epoch_state_m_m_s : np.ndarray
        Cartesian state at epoch (6,): [x, y, z, vx, vy, vz] in meters and m/s.
    time_offsets_s : np.ndarray
        Time offsets from epoch in seconds, shape (N,).
    target_positions_m : np.ndarray
        Target positions in meters, shape (N, 3).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray
        Position residuals, shape (N*3,) in meters.
    """
    keplerian_elements: np.ndarray = kepler.cartesian_to_keplerian(
        epoch_state_m_m_s, mu_m3_s2
    )

    n_samples: int = len(time_offsets_s)
    residuals: np.ndarray = np.zeros(n_samples * 3)

    for i, dt_s in enumerate(time_offsets_s):
        propagated_elements: np.ndarray = kepler.propagate_kepler(
            keplerian_elements, dt_s, mu_m3_s2
        )
        predicted_state: np.ndarray = kepler.keplerian_to_cartesian(
            propagated_elements, mu_m3_s2
        )
        residuals[i * 3 : i * 3 + 3] = target_positions_m[i] - predicted_state[:3]

    return residuals


def fit_osculating_kepler(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    max_iterations: int = 50,
) -> tuple[np.ndarray, fit_common.FitDiagnostics]:
    """Fit osculating Keplerian elements to an OEM arc using two-body propagation.

    This variant enforces that the *epoch position* matches the first OEM
    position exactly (|Δr|(t=0) = 0), while allowing the *epoch velocity* to be
    adjusted to best-fit the remainder of the arc under a two-body Kepler model.

    Concretely, we estimate only the 3 velocity components at epoch and keep
    the epoch position fixed.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples.
        State vectors are [x, y, z, vx, vy, vz] in meters and m/s.
    fit_span_s : float
        Maximum arc span in seconds (default: 7200 = 2 hours).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    max_iterations : int
        Maximum Gauss-Newton iterations.

    Returns
    -------
    tuple[np.ndarray, fit_common.FitDiagnostics]
        - Fitted osculating Keplerian elements at epoch (6,):
          [a, e, i, omega, RAAN, theta].
          Semi-major axis in meters, angles in radians.
        - FitDiagnostics dataclass with fields:
          'rms_position_m', 'iterations', 'n_records', 'span_s',
          'epoch_pos_delta_m', 'epoch_vel_delta_m_s'.
    """
    # Filter records to fit span
    reference_timestamp: float = states[0][0]
    filtered_states: list[tuple[float, np.ndarray]] = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    num_records: int = len(filtered_states)
    if num_records < 2:
        raise ValueError("At least 2 state vectors required for fitting.")

    first_state: np.ndarray = filtered_states[0][1]
    fixed_r0: np.ndarray = first_state[:3].copy()
    current_v0: np.ndarray = first_state[3:6].copy()

    # Fit over t>0 only
    time_offsets_s: np.ndarray = np.array(
        [ts - reference_timestamp for ts, _ in filtered_states[1:]]
    )
    target_positions_m: np.ndarray = np.array([sv[:3] for _, sv in filtered_states[1:]])

    if len(time_offsets_s) == 0:
        elements: np.ndarray = kepler.cartesian_to_keplerian(first_state, mu_m3_s2)
        diagnostics: fit_common.FitDiagnostics = fit_common.FitDiagnostics(
            rms_position_m=0.0,
            iterations=1,
            n_records=num_records,
            span_s=0.0,
        )
        return elements, diagnostics

    # Finite-difference step sizes for numerical Jacobian (velocity only).
    # 1 mm/s perturbation balances truncation vs. round-off error for LEO orbits.
    fd_steps_v: np.ndarray = np.array([1.0e-3, 1.0e-3, 1.0e-3])

    best_v0: np.ndarray = current_v0.copy()
    best_rms: float = np.inf
    prev_rms: float = np.inf
    final_iter: int = 0

    # ===================================================================
    # Gauss-Newton iteration loop
    # ===================================================================
    # Each iteration: evaluate residuals, build numerical Jacobian, solve
    # normal equations with diagonal damping, and apply a line search.
    for iteration in range(max_iterations):
        epoch_state: np.ndarray = np.hstack((fixed_r0, current_v0))
        residuals: np.ndarray = _compute_kepler_residuals_from_epoch_state(
            epoch_state, time_offsets_s, target_positions_m, mu_m3_s2
        )
        rms: float = float(np.sqrt(np.mean(residuals**2)))

        if rms < best_rms:
            best_rms = rms
            best_v0 = current_v0.copy()

        # Convergence check: relative change in RMS below machine-precision threshold
        if iteration > 0 and abs(prev_rms - rms) / max(rms, 1.0) < 1.0e-12:
            final_iter = iteration
            break
        prev_rms = rms
        final_iter = iteration

        # Build numerical Jacobian J ∈ ℝ^(3N × 3) via forward finite differences.
        # Column p = ∂residuals/∂v₀[p], approximated as (f(v₀+δeₚ) - f(v₀)) / δ.
        n_residuals: int = len(residuals)
        jacobian: np.ndarray = np.zeros((n_residuals, 3))
        for p in range(3):
            perturbed_v0: np.ndarray = current_v0.copy()
            perturbed_v0[p] += fd_steps_v[p]
            perturbed_state: np.ndarray = np.hstack((fixed_r0, perturbed_v0))
            perturbed_residuals: np.ndarray = (
                _compute_kepler_residuals_from_epoch_state(
                    perturbed_state, time_offsets_s, target_positions_m, mu_m3_s2
                )
            )
            jacobian[:, p] = (perturbed_residuals - residuals) / fd_steps_v[p]

        # Solve normal equations: (JᵀJ + λ·diag(JᵀJ)) Δv = Jᵀr
        # The diagonal damping (Levenberg-Marquardt style, λ = 1e-8) regularizes
        # near-singular JᵀJ without significantly biasing the solution.
        jt_j: np.ndarray = jacobian.T @ jacobian
        jt_r: np.ndarray = jacobian.T @ residuals

        diagonal: np.ndarray = np.diag(jt_j).copy()
        diagonal[diagonal < 1.0e-20] = 1.0e-20  # Prevent zero-division in damping
        jt_j += np.diag(1.0e-8 * diagonal)

        try:
            correction: np.ndarray = np.linalg.solve(jt_j, jt_r)
        except np.linalg.LinAlgError:
            break

        # Backtracking line search with physical feasibility guards.
        # Halve the step up to 10 times until the trial orbit is both
        # physically valid and reduces the RMS residual.
        scale: float = 1.0
        improved: bool = False
        for _ in range(10):
            trial_v0: np.ndarray = current_v0 - scale * correction
            trial_state: np.ndarray = np.hstack((fixed_r0, trial_v0))

            # Guard: reject states that cannot be converted to valid Keplerian elements
            # (e.g., hyperbolic escape with negative semi-major axis)
            try:
                trial_elements: np.ndarray = kepler.cartesian_to_keplerian(
                    trial_state, mu_m3_s2
                )
            except Exception:
                scale *= 0.5
                continue

            # Guard: eccentricity must be in (0, 1) for a bound elliptical orbit
            e_trial: float = float(trial_elements[kepler.ECCENTRICITY_INDEX])
            a_trial: float = float(trial_elements[kepler.SEMI_MAJOR_AXIS_INDEX])
            if not (1.0e-8 <= e_trial < 0.9999):
                scale *= 0.5
                continue
            # Guard: semi-major axis must be above Earth's surface (~6000 km)
            if not (a_trial >= 6.0e6):
                scale *= 0.5
                continue

            trial_residuals: np.ndarray = _compute_kepler_residuals_from_epoch_state(
                trial_state, time_offsets_s, target_positions_m, mu_m3_s2
            )
            trial_rms: float = float(np.sqrt(np.mean(trial_residuals**2)))
            if trial_rms < rms:
                current_v0 = trial_v0
                improved = True
                break
            scale *= 0.5

        if not improved:
            break

    # Convert the best-fit Cartesian state back to Keplerian elements
    best_state: np.ndarray = np.hstack((fixed_r0, best_v0))
    elements: np.ndarray = kepler.cartesian_to_keplerian(best_state, mu_m3_s2)

    # Evaluate final residuals for diagnostics
    final_residuals: np.ndarray = _compute_kepler_residuals_from_epoch_state(
        best_state, time_offsets_s, target_positions_m, mu_m3_s2
    )
    final_rms: float = float(np.sqrt(np.mean(final_residuals**2)))

    diagnostics: fit_common.FitDiagnostics = fit_common.FitDiagnostics(
        rms_position_m=final_rms,
        iterations=final_iter + 1,
        n_records=num_records,
        span_s=float(time_offsets_s[-1]),
        epoch_pos_delta_m=0.0,
        epoch_vel_delta_m_s=float(np.linalg.norm(best_v0 - first_state[3:6])),
    )

    return elements, diagnostics


def compute_kepler_propagation_comparison(
    keplerian_elements: np.ndarray,
    states: list[tuple[float, np.ndarray]],
    mu_m3_s2: float,
    fit_span_s: float,
    interval_s: float = 600.0,
) -> list[fit_common.PropagationComparison]:
    """Compare Kepler-propagated states with OEM states at regular intervals.

    Propagates the fitted Keplerian elements at the specified interval and
    finds the closest OEM state for comparison.

    Parameters
    ----------
    keplerian_elements : np.ndarray
        Osculating Keplerian elements at epoch (6,): [a, e, i, omega, RAAN, theta].
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples from OEM.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    fit_span_s : float
        Maximum arc span in seconds.
    interval_s : float
        Comparison interval in seconds (default: 600 = 10 minutes).

    Returns
    -------
    list[fit_common.PropagationComparison]
        List of comparison records, each containing:
        - 'elapsed_s': elapsed time from epoch (s)
        - 'elapsed_min': elapsed time from epoch (min)
        - 'pos_err_km': position error magnitude (km)
        - 'vel_err_m_s': velocity error magnitude (m/s)
        - 'dx_km', 'dy_km', 'dz_km': position component errors (km)
        - 'dvx_m_s', 'dvy_m_s', 'dvz_m_s': velocity component errors (m/s)
    """
    reference_timestamp: float = states[0][0]

    # Filter states to fit span
    filtered_states: list[tuple[float, np.ndarray]] = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    if not filtered_states:
        return []

    max_elapsed: float = filtered_states[-1][0] - reference_timestamp

    # Generate comparison times at the specified interval
    comparison_times_s: list[float] = []
    current_time_s: float = 0.0
    while current_time_s <= max_elapsed:
        comparison_times_s.append(current_time_s)
        current_time_s += interval_s
    # Include the final time if not already included
    if comparison_times_s[-1] < max_elapsed:
        comparison_times_s.append(max_elapsed)

    results: list[fit_common.PropagationComparison] = []

    for elapsed_s in comparison_times_s:
        # Find closest OEM state
        target_timestamp: float = reference_timestamp + elapsed_s
        closest_state: tuple[float, np.ndarray] | None = None
        closest_diff: float = float("inf")

        for ts, sv in filtered_states:
            diff: float = abs(ts - target_timestamp)
            if diff < closest_diff:
                closest_diff = diff
                closest_state = (ts, sv)

        # Skip if no close match (tolerance: half the OEM step)
        if closest_state is None or closest_diff > interval_s / 2.0:
            continue

        actual_elapsed_s: float = closest_state[0] - reference_timestamp
        oem_state: np.ndarray = closest_state[1]

        # Propagate Keplerian elements
        propagated_elements: np.ndarray = kepler.propagate_kepler(
            keplerian_elements, actual_elapsed_s, mu_m3_s2
        )
        predicted_state: np.ndarray = kepler.keplerian_to_cartesian(
            propagated_elements, mu_m3_s2
        )

        # Compute differences
        pos_diff_m: np.ndarray = oem_state[:3] - predicted_state[:3]
        vel_diff_m_s: np.ndarray = oem_state[3:6] - predicted_state[3:6]

        pos_err_m: float = float(np.linalg.norm(pos_diff_m))
        vel_err_m_s: float = float(np.linalg.norm(vel_diff_m_s))

        results.append(
            fit_common.PropagationComparison(
                elapsed_s=actual_elapsed_s,
                elapsed_min=actual_elapsed_s / 60.0,
                pos_err_km=pos_err_m / 1000.0,
                vel_err_m_s=vel_err_m_s,
                dx_km=pos_diff_m[0] / 1000.0,
                dy_km=pos_diff_m[1] / 1000.0,
                dz_km=pos_diff_m[2] / 1000.0,
                dvx_m_s=vel_diff_m_s[0],
                dvy_m_s=vel_diff_m_s[1],
                dvz_m_s=vel_diff_m_s[2],
            )
        )

    return results


def format_kepler_output(
    epoch: datetime,
    keplerian_elements: np.ndarray,
    diagnostics: fit_common.FitDiagnostics,
    comparison: list[fit_common.PropagationComparison] | None = None,
) -> str:
    """Format osculating Keplerian elements as human-readable text.

    Parameters
    ----------
    epoch : datetime
        Reference epoch.
    keplerian_elements : np.ndarray
        Osculating Keplerian elements (6,): [a, e, i, omega, RAAN, theta].
    diagnostics : fit_common.FitDiagnostics
        Fit diagnostics (FitDiagnostics dataclass or dict with compatible keys).
    comparison : list[fit_common.PropagationComparison] | None
        Propagation comparison results from compute_propagation_comparison.

    Returns
    -------
    str
        Multi-line formatted output.
    """
    lines: list[str] = []
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    # Extract Keplerian elements using standard orbital mechanics notation
    a_m: float = keplerian_elements[kepler.SEMI_MAJOR_AXIS_INDEX]  # Semi-major axis (m)
    e: float = keplerian_elements[
        kepler.ECCENTRICITY_INDEX
    ]  # Eccentricity (dimensionless)
    i_rad: float = keplerian_elements[kepler.INCLINATION_INDEX]  # Inclination (rad)
    omega_rad: float = keplerian_elements[
        kepler.ARGUMENT_OF_PERIAPSIS_INDEX
    ]  # Argument of periapsis (rad)
    raan_rad: float = keplerian_elements[
        kepler.RAAN_INDEX
    ]  # Right ascension of ascending node (rad)
    theta_rad: float = keplerian_elements[
        kepler.TRUE_ANOMALY_INDEX
    ]  # True anomaly (rad)

    # Handle both dataclass and dict for diagnostics
    if isinstance(diagnostics, dict):
        n_records = diagnostics["n_records"]
        span_s = diagnostics["span_s"]
        iterations = diagnostics["iterations"]
        rms_position_m = diagnostics["rms_position_m"]
        epoch_vel_delta_m_s = diagnostics.get("epoch_vel_delta_m_s")
    else:
        n_records = diagnostics.n_records
        span_s = diagnostics.span_s
        iterations = diagnostics.iterations
        rms_position_m = diagnostics.rms_position_m
        epoch_vel_delta_m_s = diagnostics.epoch_vel_delta_m_s

    lines.append("Osculating Keplerian elements (two-body fit):")
    lines.append(f"  epoch:              {epoch_str}")
    lines.append(f"  records used:       {n_records}")
    lines.append(f"  arc span:           {span_s:.1f} s")
    lines.append(f"  iterations:         {iterations}")
    lines.append(f"  RMS position error: {rms_position_m / 1000.0:.6f} km")
    if epoch_vel_delta_m_s is not None:
        lines.append(f"  epoch Δ|v0|:         {epoch_vel_delta_m_s:.6f} m/s")
    lines.append("")
    lines.append("  Elements (km, degrees):")
    lines.append(f"    semi-major axis:       {a_m / 1000.0:.6f} km")
    lines.append(f"    eccentricity:          {e:.10f}")
    lines.append(f"    inclination:           {np.degrees(i_rad):.6f} deg")
    lines.append(f"    arg of periapsis:      {np.degrees(omega_rad):.6f} deg")
    lines.append(f"    RAAN:                  {np.degrees(raan_rad):.6f} deg")
    lines.append(f"    true anomaly:          {np.degrees(theta_rad):.6f} deg")

    # Derived quantities
    mean_motion_rev_day: float = kepler.semi_major_axis_to_mean_motion(a_m)
    mean_motion_rad_s: float = mean_motion_rev_day * 2.0 * np.pi / 86400.0
    lines.append("")
    lines.append("  Derived quantities:")
    lines.append(f"    mean motion:           {mean_motion_rev_day:.10f} rev/day")
    lines.append(f"    orbital period:        {2.0 * np.pi / mean_motion_rad_s:.3f} s")

    # Propagation comparison table
    if comparison:
        lines.append("")
        lines.append("  Propagation comparison (Kepler vs OEM) at 10-minute intervals:")
        lines.append("")
        # Header
        lines.append(f"    {'t (min)':>8}  {'|Δr| (km)':>10}  {'|Δv| (km/s)':>12}")
        lines.append(f"    {'─' * 8}  {'─' * 10}  {'─' * 12}")

        for rec in comparison:
            lines.append(
                f"    {rec.elapsed_min:8.1f}  "
                f"{rec.pos_err_km:10.6f}  "
                f"{rec.vel_err_m_s / 1000.0:12.9f}"
            )

        # Summary statistics
        pos_errors: list[float] = [r.pos_err_km for r in comparison]
        vel_errors_km_s: list[float] = [r.vel_err_m_s / 1000.0 for r in comparison]
        lines.append("")
        lines.append("  Summary:")
        lines.append(
            f"    Position |Δr|:  min = {min(pos_errors):.6f} km   "
            f"max = {max(pos_errors):.6f} km   "
            f"avg = {np.mean(pos_errors):.6f} km"
        )
        lines.append(
            f"    Velocity |Δv|:  min = {min(vel_errors_km_s):.9f} km/s   "
            f"max = {max(vel_errors_km_s):.9f} km/s   "
            f"avg = {np.mean(vel_errors_km_s):.9f} km/s"
        )

    return "\n".join(lines)
