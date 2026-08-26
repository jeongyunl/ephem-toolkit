# OEM to OMM Conversion

Comprehensive documentation for the `oem_to_omm` module, which estimates Orbit Mean-Elements Messages (OMM) including Two-Line Element (TLE) sets from OEM-like Cartesian state vectors.

## Overview

The `oem_to_omm` module provides tools for converting orbit ephemeris data in OEM (Orbit Ephemeris Message) format or raw Cartesian state vectors into OMM (Orbit Mean-Elements Message) format, including TLE (Two-Line Element) format. This is a non-trivial estimation problem because TLEs encode SGP4-compatible mean orbital elements rather than osculating Cartesian states.

## Module Structure

The `src/oem_to_omm/` directory contains:

- `oem-to-omm` — Main executable script for OMM/TLE estimation
- `fit_common.py` — Common fitting utilities
- `fit_mean_kepler.py` — Mean Keplerian element fitting
- `fit_tle_main.py` — TLE fitting main entry point
- `fit_tle/` — TLE fitting submodule containing:
  - `constants.py` — Physical and mathematical constants
  - `estimation.py` — Core estimation algorithms for TLE elements
  - `linalg.py` — Linear algebra utilities
  - `models.py` — Data models and dataclasses
  - `orbital_mechanics.py` — Orbital mechanics calculations
  - `refinement.py` — Refinement algorithms for epoch state matching
  - `tle_builder.py` — TLE construction and formatting

## Main Script: `oem-to-omm`

### Purpose

Converts OEM state vectors to mean-element OMM format. Supports two modes:

- **`--mode mean-kepler`**: Fits mean Keplerian elements using J2 secular propagation
- **`--mode tle`**: Fits TLE mean elements (SGP4-compatible) to create an OMM with TLE parameters

For osculating Keplerian element fitting, use [`oem-to-opm`](OEM_TO_OPM.md).

### Synopsis

```bash
oem-to-omm [-h] [-o <output_omm|->] [-v]
                                 [--mu <value>] [--fit-span <hours>]
                                 --mode {mean-kepler,tle}
                                 [--object-name <name>] [--object-id <YYYY-NNNP>]
                                 [--tle-refinement <none|cartesian|keplerian>]
                                 [--tle-norad-cat-id <0..99999>]
                                 [--tle-classification-type <U|C|S>]
                                 [--tle-ephemeris-type <0..9>]
                                 [--tle-element-set-no <0..9999>]
                                 [--tle-rev-at-epoch <0..99999>]
                                 <input_oem|->
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input_oem>` | Path to input CCSDS OEM file (use `-` to read from stdin) |
| `-o`, `--output` | Save fitted elements in OMM format to file or `-` for stdout (required) |
| `-v`, `--verbose` | Print detailed debug information to stderr |
| `--mu` | Gravitational parameter in m³/s² (default: Earth WGS-84) |
| `--fit-span` | Maximum arc span in hours for fitting (default: 2.0) |
| `--mode {mean-kepler,tle}` | Select conversion mode: mean-Kepler fit or TLE fit |
| `--object-name` | OBJECT_NAME: Spacecraft name for OMM output |
| `--object-id` | OBJECT_ID: International designator (e.g., 1998-067A) |
| `--tle-refinement` | Refinement method for TLE fitting: `cartesian` (default), `keplerian`, or `none` |
| `--tle-norad-cat-id` | NORAD_CAT_ID: NORAD Catalog Number (0-99999, default: 0) |
| `--tle-classification-type` | CLASSIFICATION_TYPE: `U`, `C`, or `S` (default: `U`) |
| `--tle-ephemeris-type` | EPHEMERIS_TYPE: 0=SGP, 2=SGP4, 4=SGP4-XP, 6=SP (default: 2) |
| `--tle-element-set-no` | ELEMENT_SET_NO: Element set number (0-9999, default: 999) |
| `--tle-rev-at-epoch` | REV_AT_EPOCH: Revolution number at epoch (0-99999, default: 0) |

### Input Format

The script accepts two input formats:

#### 1. CCSDS OEM Format

Standard CCSDS Orbit Ephemeris Message format with metadata header and state vectors.

#### 2. Raw State Vectors

Whitespace- or comma-delimited lines with 7 fields:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Example:

```text
2026-05-20T12:00:00.000000 -4016.835 3234.040 5296.436 5.300 -1.578 4.969
2026-05-20T12:01:00.000000 -3698.123 3145.678 5512.345 5.234 -1.892 4.856
```

Notes:
- Blank lines and lines beginning with `#` are ignored
- Trailing `Z` on timestamps is accepted and stripped
- At least 2 state vectors are required

### Output Format

Standard two-line element format:

```text
SATELLITE NAME (optional)
1 NNNNNC UUUUU CCCC NNNNN.NNNNNNNN  .NNNNNNNN  NNNNN-N NNNNN-N N NNNNN
2 NNNNN NNN.NNNN NNN.NNNN NNNNNNN NNN.NNNN NNN.NNNN NN.NNNNNNNNNNNNNN
```

### Refinement Methods

The script supports three TLE refinement strategies selected with `--tle-refinement` for matching TLE elements to the epoch state:

#### Cartesian refinement (`--tle-refinement cartesian`, default)

- Minimizes SGP4 Cartesian state residual at epoch
- Requires TudatPy for SGP4 propagation
- Provides highest accuracy for position and velocity matching
- Uses Gauss-Newton iteration with backtracking line search
- Typical accuracy: sub-meter position, sub-mm/s velocity

#### Keplerian refinement (`--tle-refinement keplerian`)

- Minimizes osculating Keplerian element residual
- Uses `core.convert_tle.tle_to_osculating_keplerian` with J2 short-period corrections
- No SGP4/TudatPy dependency (pure Python + NumPy)
- Excellent angular accuracy (sub-millidegree)
- Semi-major axis accuracy limited to ~2 km by first-order Brouwer approximation

#### No refinement (`--tle-refinement none`)

- Skips epoch state matching entirely
- Uses only regression-based mean element estimation
- Fastest but least accurate
- Useful for quick estimates or when refinement dependencies are unavailable

### Estimation Pipeline

The script follows a four-stage workflow:

1. **Parse Input** — Read and validate OEM-like state vectors
2. **Initial Estimation** — Compute mean elements via regression and circular statistics
3. **Refinement** — Match TLE epoch state to source epoch state (optional)
4. **B* Estimation** — Optimize drag term to minimize propagation error over arc

### Dependencies

- TudatPy (for SGP4 propagation)
- NumPy
- `ephem_toolkit.core.ccsds.oem`, `ephem_toolkit.core.consts`, `ephem_toolkit.core.time_utils`, `ephem_toolkit.core.tle`
- `oem_to_omm.fit_common`, `oem_to_omm.fit_tle_main`
- `oem_to_omm.fit_tle` submodule components

## Algorithm Details

For detailed information about the estimation algorithms, refinement strategies, and implementation details, see the sections above.

Key algorithmic features:

- **Secular trend fitting** — Ordinary least-squares regression for mean motion, RAAN, and argument of latitude
- **Circular statistics** — Robust angle estimation avoiding 0°/360° discontinuities
- **Phase matching** — Short-period filtering via orbital phase alignment
- **J2 nodal precession** — Mean inclination inference from RAAN drift
- **Gauss-Newton refinement** — Iterative epoch state matching with backtracking line search
- **B* optimization** — Drag term estimation via arc propagation error minimization

## Related Tools

- `ephem_toolkit.core.tle` — TLE dataclass, `read_tle()`, and `write_tle()` functions
- `ephem_toolkit.core.ccsds.omm` — OMM dataclass and utilities
- `ephem_toolkit.core.kepler` — Keplerian element conversions with J2 corrections
- `ephem_toolkit.core.ccsds.oem` — OEM parsing utilities
- `propagate-tle` — TLE propagation with SGP4
- `propagate-omm` — Propagate an OMM or TLE input using the appropriate solver automatically
- `omm-to-tle` — Convert OMM to TLE
- `tle-to-omm` — Convert TLE to OMM

## Best Practices

### Input Data Quality

- Use at least 2 state vectors (more is better for trend estimation)
- Span at least one orbital period for accurate mean motion estimation
- Ensure consistent time spacing for best regression results
- Verify input coordinates are in the correct reference frame (typically J2000/GCRF)

### Refinement Method Selection

- Use **Cartesian refinement** when TudatPy is available and highest accuracy is needed
- Use **Keplerian refinement** for pure Python workflows or when TudatPy is unavailable
- Use **no refinement** only for quick estimates or testing

### B* Drag Term

- Let the script estimate B* from the arc for best propagation accuracy
- Manually specify B* only when you have external drag information
- For short arcs (<1 day), B* estimation may be unreliable

### Metadata

- Provide accurate satellite metadata (NORAD number, international designator) when available
- Use meaningful satellite names for better TLE identification
- Increment element set number for successive TLE generations

## Troubleshooting

### "Need at least 2 OEM-like state vectors"

- Ensure input file contains at least 2 valid state lines
- Check that lines are not commented out with `#`
- Verify epoch format is ISO 8601 compatible

### "Invalid epoch" errors

- Ensure timestamps are in ISO 8601 format: `YYYY-MM-DDTHH:MM:SS.ffffff`
- Trailing `Z` is optional and will be stripped automatically
- Check for typos in date/time fields

### Poor refinement convergence

- Increase arc span for better mean element estimation
- Try different refinement methods
- Check input data quality and consistency

### Large propagation errors

- Verify input reference frame matches TLE expectations (J2000/GCRF)
- Check for data gaps or outliers in input arc
- Consider using longer arc for B* estimation

## Performance Considerations

- **Cartesian refinement**: ~1-2 seconds per TLE (depends on convergence)
- **Keplerian refinement**: ~0.5-1 second per TLE
- **No refinement**: <0.1 seconds per TLE

Refinement time scales with:
- Number of iterations required for convergence
- Arc length (for B* estimation)
- Number of input state vectors

## References

- [CCSDS OEM Blue Book](https://public.ccsds.org/Pubs/502x0b2c1e2.pdf)
- [TLE Format Specification](https://celestrak.org/NORAD/documentation/tle-fmt.php)
- [SGP4 Theory](https://celestrak.org/publications/AIAA/2006-6753/)
- Brouwer, D. (1959). "Solution of the problem of artificial satellite theory without drag"

## See Also

- [README.md](../README.md) — Repository overview

Detailed algorithm and strategy documentation is included below.

## Detailed TLE Estimation Notes

### Purpose

`oem-to-omm` estimates a valid Two-Line Element (TLE) set from a time series of OEM-like Cartesian state vectors:

```text
UTC_ISO x y z vx vy vz
```

with position in km and velocity in km/s.

Unlike directly calling `core.tle.write_tle()` with explicit fields, `oem-to-omm` attempts to infer a TLE from a Cartesian arc.

This is fundamentally an estimation problem because TLEs encode SGP4-compatible mean elements rather than raw osculating Cartesian states.

### Repository context

Related scripts in the current repository:

- `oem-to-omm` — estimate a TLE from an OEM-like arc
- `ephem_toolkit.core.tle` — shared `Tle` dataclass, `read_tle()`, and `write_tle()` functions
- `propagate-tle` — propagate a TLE with TudatPy SGP4 and print OEM-like states
- `propagate-omm` — propagate an OMM or TLE input and emit OEM output with automatic solver selection

### Overall pipeline

The script follows a four-stage workflow:

1. Parse the input OEM-like state vectors.
2. Estimate initial mean TLE elements from the osculating arc.
3. Refine the line-2 elements so the TLE epoch state better matches the source epoch state.
4. Estimate `B*` by minimizing propagation error over the arc.

Finally, it prints diagnostics and writes the TLE using `core.tle.write_tle()`.

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

Two refinement methods are available, selected via `--tle-refinement`:

### 3a. Cartesian refinement (`--tle-refinement cartesian`, default)

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

### 3b. Keplerian refinement (`--tle-refinement keplerian`)

### `refine_estimated_fields_keplerian_match`

An alternative refinement that does **not** require SGP4/TudatPy. Instead, it minimizes the residual between the TLE's osculating Keplerian elements (computed via `core.convert_tle.tle_to_osculating_keplerian` with J2 short-period corrections) and the reference osculating elements derived from the input Cartesian state.

### Algorithm outline

1. Compute reference osculating Keplerian elements from the epoch Cartesian state using `core.kepler.cartesian_to_keplerian`.
2. Build a candidate TLE from the current parameter estimate.
3. Convert TLE mean elements to osculating elements via `core.convert_tle.tle_to_osculating_keplerian` (applies Brouwer first-order J2 short-period corrections).
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
- `core.tle.write_tle()` is the formatting/checksum authority.
- Circular statistics are used extensively to avoid 0°/360° discontinuity problems.
- The estimator is designed to degrade gracefully when some higher-fidelity refinement steps are unavailable.

## Practical takeaway

Use:

- `core.tle.write_tle()` when you already know the TLE fields and want to write them programmatically
- `oem-to-omm` when you have an OEM-like Cartesian arc and want an estimated TLE
- `core.tle.read_tle()` when you want to parse an existing TLE into structured fields

### Usage Examples

**Fit mean Keplerian elements (`--mode mean-kepler`):**

```bash
oem-to-omm --mode mean-kepler input.oem -o output.omm
```

**Fit TLE elements (`--mode tle`) with default Cartesian refinement:**

```bash
oem-to-omm --mode tle input.oem -o output.omm
```

**Fit TLE and output TLE lines to stdout:**

```bash
oem-to-omm --mode tle input.oem
```

**Read from stdin, fit TLE, output to stdout:**

```bash
cat input.oem | oem-to-omm --mode tle - -o -
```

**Fit TLE with Keplerian refinement (no TudatPy required):**

```bash
oem-to-omm --mode tle --tle-refinement keplerian input.oem
```

**Fit TLE with no refinement (fastest):**

```bash
oem-to-omm --mode tle --tle-refinement none input.oem
```

**Specify satellite metadata for TLE:**

```bash
oem-to-omm --mode tle input.oem -o output.omm \
  --object-name "ISS (ZARYA)" \
  --object-id "1998-067A" \
  --tle-norad-cat-id 25544 \
  --tle-classification-type U \
  --tle-element-set-no 999
```

**Fit with custom fit span (3 hours):**

```bash
oem-to-omm --mode tle --fit-span 3.0 input.oem
```

**Verbose output to stderr:**

```bash
oem-to-omm --mode tle -v input.oem -o output.omm
```

### Dependencies

- Python standard library
- NumPy (for numerical computations)
- `ephem_toolkit.core.tle` — TLE dataclass and formatting
- `ephem_toolkit.core.kepler` — Keplerian element conversions
- `ephem_toolkit.core.ccsds.oem` — OEM parsing
- TudatPy (optional, required for `--tle-refinement cartesian`)
