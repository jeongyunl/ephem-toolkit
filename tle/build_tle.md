## `build_tle.py` — Approach, Algorithms, and Strategy

### Purpose

This script converts a time-series of **OEM-like Cartesian state vectors** (position and velocity in km and km/s, with ISO-8601 timestamps) into a valid **Two-Line Element (TLE)** set. TLEs are the standard compact format used by the SGP4/SDP4 propagator for Earth-orbiting satellites. The core challenge is that TLEs encode *mean* (averaged) Keplerian elements tuned to the SGP4 analytical model, not osculating (instantaneous) elements, so a direct Cartesian-to-Keplerian conversion is insufficient.

### Overall Pipeline (Strategy)

The `main()` function orchestrates a **four-stage pipeline**:

1. **Parse** the input OEM state vectors.
2. **Estimate** initial mean TLE elements from the arc of osculating states.
3. **Refine** the elements via Gauss–Newton iteration to match the SGP4-propagated epoch state to the true epoch state.
4. **Estimate B\*** (drag coefficient) by minimizing propagation error over the full arc.

Finally, it prints a diagnostic summary and either outputs the TLE to stdout or invokes `write_tle.py` to write it to a file.

---

### Stage 1 — Parsing (`parse_dataset`, `parse_oem_state_line`)

- Reads whitespace/comma-delimited lines of the form `UTC_ISO x y z vx vy vz` (km, km/s).
- Strips trailing `Z` from ISO timestamps, parses with `datetime.fromisoformat`.
- Requires ≥ 2 records to establish trends.

---

### Stage 2 — Initial Mean Element Estimation (`estimate_tle_fields`)

This is the most algorithmically rich stage. It converts each Cartesian state to osculating Keplerian elements and then applies several statistical and astrodynamics techniques to extract *mean* elements at the first epoch:

#### 2a. Osculating Keplerian Conversion (`state_to_orbital_elements`)
Standard textbook algorithm:
- Computes angular momentum **h** = **r** × **v**, node vector **n** = **k̂** × **h**, eccentricity vector **e** = (**v** × **h**)/μ − **r̂**.
- Derives semi-major axis from vis-viva, inclination from h_z/|h|, RAAN from node vector, argument of perigee and true anomaly from dot/cross products.
- Converts true anomaly → eccentric anomaly → mean anomaly via Kepler's equation (M = E − e·sin E).

#### 2b. Secular Trend Fitting via Linear Regression
- **Mean motion**: Ordinary least-squares (OLS) linear regression of osculating mean motion vs. time gives the secular drift rate (used for the TLE's `ndot/2` field) and the intercept at epoch.
- **RAAN**: Unwraps the RAAN angle series (to handle 0°/360° wrapping), then fits a linear trend. The intercept gives the mean RAAN at epoch.
- **Argument of latitude** (ω + M): Unwrapped and linearly regressed to get a rate (effectively another estimate of mean motion from the angular domain).

#### 2c. Mean Motion Blending
Two complementary estimates of mean motion at epoch are averaged:
- The energy-derived regression intercept (from semi-major axis / vis-viva).
- The argument-of-latitude angular rate converted to rev/day.

This 50/50 blend reduces short-period oscillation bias inherent in either estimate alone.

#### 2d. Phase Detrending for Epoch Angles
For RAAN, argument of perigee, and mean anomaly, the script removes the fitted secular rate from each sample, then computes the **circular mean** of the residuals. This yields a phase estimate that is robust to short-period oscillations. Mean anomaly is further stabilized by averaging the detrended circular mean with the raw osculating value at epoch.

#### 2e. Phase-Matching at Repeated Orbital Phases (`phase_match_epoch_angles`)
The script identifies records that recur at approximately the same orbital phase (argument of latitude) as the first record, separated by integer orbit periods. It circular-averages the osculating RAAN, ω, and M at those phase-matched points. This acts as a **short-period filter**: by sampling at the same orbital phase, short-period perturbations (which are periodic in true/mean anomaly) cancel out.

The phase-matched angles are **blended** with the regression-based angles using a soft weight: `w = count / (count + 6)`. This means the phase-match correction grows stronger as more matching revolutions are available, but never fully overrides the regression estimate.

#### 2f. Inclination from Nodal Precession (`estimate_inclination_from_nodal_drift`)
Rather than using the osculating inclination (which has short-period oscillations), the script inverts the J2 secular nodal precession formula:

> dΩ/dt = −1.5 · J2 · n · (R_E / p)² · cos(i)

The RAAN drift rate (from linear regression) is used to solve for cos(i), yielding a *mean* inclination consistent with the observed nodal regression. Falls back to the osculating value if the inversion is out of range.

#### 2g. Mean Motion First Derivative
The OLS slope of mean motion vs. time (in rev/day²) is halved to produce the TLE's `ndot/2` field, clamped to the TLE representable range.

---

### Stage 3 — Gauss–Newton State-Match Refinement (`refine_estimated_fields_to_match_epoch_state`)

The initial mean elements are approximate. This stage iteratively adjusts the six line-2 parameters (i, Ω, e, ω, M, n) so that when the resulting TLE is propagated by SGP4 to its own epoch, the output Cartesian state matches the true (input) epoch state.

**Algorithm:**
1. Build a candidate TLE from current parameters, propagate it with SGP4 (via TudatPy), and compute the 6-component residual (target − SGP4 state).
2. Compute a **6×6 Jacobian** via central finite differences: for each parameter, perturb ±Δ, build two TLEs, propagate both, and estimate ∂state/∂param.
3. Form a **weighted least-squares** normal equation (position weight = 1, velocity weight = 1000 to balance km vs. km/s scales).
4. Solve the normal equations with Gaussian elimination (with Tikhonov regularization ε = 10⁻¹²).
5. Apply a **backtracking line search** (scales 1.0, 0.5, 0.25, 0.1) with step clamping (±5× the finite-difference step) to ensure monotonic cost decrease.
6. Repeat up to 80 iterations or until no line-search scale improves the cost.

All TLE evaluations are batched (multiple TLEs evaluated in a single call to `evaluate_tle_epoch_states_km`) to reduce overhead.

---

### Stage 4 — B\* Drag Estimation (`estimate_bstar_from_arc`)

If B\* is not explicitly provided, the script estimates it by minimizing the total propagation error over the arc:

1. Select up to 9 evenly-spaced post-epoch sample points from the input arc (`select_bstar_fit_samples`).
2. For each candidate B\* value, build a TLE, propagate it to all sample times, and sum the weighted state residuals.
3. Use a **coordinate-descent / golden-section-like** 1D search: try stepping B\* in both directions by a step size, accept if cost decreases, otherwise halve the step. Runs up to 12 iterations, clamped to |B\*| ≤ 10⁻³.

This is a simple but effective univariate optimizer for the single drag parameter.

---

### Supporting Algorithms

| Component | Algorithm |
|---|---|
| `linear_regression_slope/intercept` | Standard OLS via sum-of-products formulas |
| `solve_linear_system` | Gaussian elimination with partial pivoting on an augmented matrix |
| `solve_weighted_least_squares` | Forms AᵀA·x = Aᵀb normal equations, adds Tikhonov regularization, solves with Gaussian elimination |
| `unwrap_angles_rad` | Sequential phase unwrapping (adds ±2π when consecutive jumps exceed π) |
| `circular_mean_angle_rad` | Computes mean direction via atan2(Σsin, Σcos) — the standard circular statistics mean |
| `circular_blend_angle_rad` | Weighted interpolation along the shortest arc between two angles |
| `format_tle_exponential_from_float` | Converts a float to the 7-character compact TLE exponential notation (e.g., `29661-4`) |

---

### Key Design Decisions

- **No external numerical libraries**: All linear algebra (Gaussian elimination, least squares) and orbital mechanics are implemented from scratch in pure Python, making the script dependency-free beyond TudatPy (which is optional and only needed for the SGP4 refinement stages).
- **Graceful degradation**: If TudatPy/SPICE is unavailable, stages 3 and 4 are skipped and the regression-based estimates are used directly.
- **Robustness to angle wrapping**: Extensive use of circular statistics (circular mean, unwrapping, shortest-arc blending) prevents discontinuity artifacts at 0°/360° boundaries.
- **Separation of concerns**: The script estimates elements and emits a `write_tle.py` command; `write_tle.py` handles TLE formatting and checksum computation independently.
