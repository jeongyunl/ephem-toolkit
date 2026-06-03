# `build_tle.py` — approach, algorithms, and strategy

## Purpose

`tle/build_tle.py` estimates a valid Two-Line Element (TLE) set from a time series of OEM-like Cartesian state vectors:

```text
UTC_ISO x y z vx vy vz
```

with position in km and velocity in km/s.

Unlike directly calling `common.tle.write_tle()` with explicit fields, `tle/build_tle.py` attempts to infer a TLE from a Cartesian arc.

This is fundamentally an estimation problem because TLEs encode SGP4-compatible mean elements rather than raw osculating Cartesian states.

## Repository context

Related scripts in the current repository:

- `tle/build_tle.py` — estimate a TLE from an OEM-like arc
- `common/tle.py` — shared `Tle` dataclass, `read_tle()`, and `write_tle()` functions
- `propagation/propagate_tle.py` — propagate a TLE with TudatPy SGP4 and print OEM-like states

## Overall pipeline

The script follows a four-stage workflow:

1. Parse the input OEM-like state vectors.
2. Estimate initial mean TLE elements from the osculating arc.
3. Refine the line-2 elements so the TLE epoch state better matches the source epoch state.
4. Estimate `B*` by minimizing propagation error over the arc.

Finally, it prints diagnostics and writes the TLE using `common.tle.write_tle()`.

---

## Stage 1 — parsing

### `parse_dataset`, `parse_oem_state_line`

- Reads whitespace- or comma-delimited lines of the form:
  - `UTC_ISO x y z vx vy vz`
- Strips a trailing `Z` from ISO timestamps when present.
- Parses timestamps into Python `datetime` values.
- Requires at least two records to estimate trends.

---

## Stage 2 — initial mean-element estimation

### `estimate_tle_fields`

This stage converts each Cartesian state to osculating Keplerian elements and then derives a mean-element estimate suitable for TLE construction.

### 2a. Osculating Keplerian conversion

### `state_to_orbital_elements`

Standard orbital-element reconstruction from Cartesian state:

- angular momentum vector `h = r x v`
- node vector
- eccentricity vector
- semi-major axis from vis-viva
- inclination, RAAN, argument of perigee, true anomaly
- eccentric anomaly and mean anomaly via Kepler's equation

### 2b. Secular trend fitting via linear regression

The script performs ordinary least-squares fits over the arc for quantities such as:

- mean motion
- RAAN
- argument of latitude

This provides secular rates and epoch intercepts.

### 2c. Mean-motion blending

Two complementary mean-motion estimates are blended:

- an energy-derived estimate
- an angular-rate estimate from argument-of-latitude evolution

This reduces sensitivity to short-period oscillations.

### 2d. Phase detrending for epoch angles

For RAAN, argument of perigee, and mean anomaly, the script removes fitted secular trends and uses circular statistics to estimate robust epoch phases.

### 2e. Phase matching at repeated orbital phases

### `phase_match_epoch_angles`

The script looks for samples that recur near the same orbital phase as the first sample and circular-averages those angles.

This acts as a short-period filter because periodic effects tend to cancel when sampled at similar orbital phase.

### 2f. Inclination from nodal precession

### `estimate_inclination_from_nodal_drift`

Instead of relying only on the osculating inclination, the script can infer a mean inclination from the observed RAAN drift using the J2 nodal precession relation.

### 2g. Mean-motion first derivative

The slope of mean motion versus time is converted into the TLE `ndot/2` field and clamped to the representable range.

---

## Stage 3 — epoch-state refinement

Two refinement methods are available, selected via `--refinement`:

### 3a. Cartesian refinement (`--refinement cartesian`, default)

### `refine_estimated_fields_to_match_epoch_state`

The initial mean elements are refined so that the TLE, when propagated by SGP4 to its own epoch, better matches the source epoch state.

### Algorithm outline

1. Build a candidate TLE from the current parameter estimate.
2. Propagate it with SGP4 to the epoch.
3. Compute the 6-component Cartesian residual.
4. Estimate a 6x6 Jacobian by central finite differences.
5. Solve a weighted least-squares update.
6. Apply a backtracking line search.
7. Repeat until convergence or iteration limit.

Implementation notes captured in the original investigation:

- position and velocity residuals are weighted differently to balance km and km/s scales
- Tikhonov-style regularization is used in the normal equations
- multiple TLE evaluations are batched where possible to reduce overhead

### 3b. Keplerian refinement (`--refinement keplerian`)

### `refine_estimated_fields_keplerian_match`

An alternative refinement that does **not** require SGP4/TudatPy. Instead, it minimizes the residual between the TLE's osculating Keplerian elements (computed via `common.kepler.tle_to_osculating_keplerian` with J2 short-period corrections) and the reference osculating elements derived from the input Cartesian state.

### Algorithm outline

1. Compute reference osculating Keplerian elements from the epoch Cartesian state using `common.kepler.cartesian_to_keplerian`.
2. Build a candidate TLE from the current parameter estimate.
3. Convert TLE mean elements to osculating elements via `common.kepler.tle_to_osculating_keplerian` (applies Brouwer first-order J2 short-period corrections).
4. Compute a 6-component residual vector (semi-major axis, eccentricity, inclination, RAAN, argument of latitude, argument of periapsis).
5. Estimate a 6×6 Jacobian by central finite differences.
6. Solve a weighted least-squares update.
7. Apply a backtracking line search.
8. Repeat until convergence or iteration limit.

Key advantages:

- No external propagator dependency (pure Python + NumPy)
- J2 short-period corrections provide a differentiable mapping from TLE mean elements to osculating elements
- Angular accuracy is excellent (sub-millidegree for argument of latitude)
- Semi-major axis accuracy is limited to ~2 km by the first-order Brouwer approximation vs SGP4's more complex model

---

## Stage 4 — `B*` estimation over the arc

### `estimate_bstar_from_arc`

If `B*` is not fixed externally, the script estimates it by minimizing propagation error over selected post-epoch samples.

### Strategy

1. Select a subset of representative arc samples.
2. For each candidate `B*`, build a TLE and propagate it to those sample times.
3. Compute a weighted total residual cost.
4. Use a simple one-dimensional search strategy to improve `B*`.

This is a pragmatic scalar optimization over the drag-like parameter.

---

## Supporting algorithms

| Component | Role |
|---|---|
| `linear_regression_slope` / `linear_regression_intercept` | Ordinary least-squares trend estimation |
| `solve_linear_system` | Gaussian elimination |
| `solve_weighted_least_squares` | Normal-equation least-squares solve with regularization |
| `unwrap_angles_rad` | Angle unwrapping across `2π` discontinuities |
| `circular_mean_angle_rad` | Circular mean via `atan2(sum sin, sum cos)` |
| `circular_blend_angle_rad` | Weighted shortest-arc blending of angles |
| `format_tle_exponential_from_float` | Compact TLE exponential formatting |

---

## Design choices

- The script separates estimation from final TLE formatting.
- `common.tle.write_tle()` is the formatting/checksum authority.
- Circular statistics are used extensively to avoid 0°/360° discontinuity problems.
- The estimator is designed to degrade gracefully when some higher-fidelity refinement steps are unavailable.

## Practical takeaway

Use:

- `common.tle.write_tle()` when you already know the TLE fields and want to write them programmatically
- `tle/build_tle.py` when you have an OEM-like Cartesian arc and want an estimated TLE
- `common.tle.read_tle()` when you want to parse an existing TLE into structured fields
