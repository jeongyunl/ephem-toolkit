# OEM to OMM Conversion

Reference for the `oem-to-omm` command and its Brouwer, DSST, and SGP4-compatible element fits.

## Overview

The `ephem_toolkit.oem_to_omm` package fits Brouwer, DSST, or SGP4-compatible mean elements to a CCSDS OEM state arc. It writes the fitted elements as a CCSDS OMM; use `omm-to-tle` to convert an SGP4 OMM to TLE text. This is an estimation problem because mean elements are not the same as the OEM's osculating Cartesian states.

## Module Structure

The `src/ephem_toolkit/oem_to_omm/` package contains:

- `__main__.py` — CLI entry point and model dispatch
- `oem_to_omm_cli.py` — CLI arguments and compatibility handling
- `fit_common.py` — Shared fitting diagnostics and utilities
- `fit_brouwer.py` — Brouwer and DSST mean-element fitting
- `fit_tle_main.py` — SGP4-compatible mean-element fitting
- `fit_tle/` — TLE estimation and refinement components:
  - `constants.py` — Physical and mathematical constants
  - `estimation.py` — Core estimation algorithms for TLE elements
  - `linalg.py` — Linear algebra utilities
  - `models.py` — Data models and dataclasses
  - `orbital_mechanics.py` — Orbital mechanics calculations
  - `refinement.py` — Refinement algorithms for epoch state matching
  - `tle_builder.py` — TLE construction and formatting

## Main Script: `oem-to-omm`

### Purpose

Fits mean elements from OEM state vectors and writes an OMM. The canonical selector is `--fit-model`:

- **`--fit-model brouwer`**: Fits Brouwer mean Keplerian elements using J2 secular propagation.
- **`--fit-model dsst`**: Fits DSST mean elements with J2 perturbations enabled.
- **`--fit-model sgp4`** (default): Fits SGP4-compatible mean elements and TLE parameters, then writes them as an OMM.

`--mode` is a deprecated alias for `--fit-model`; its legacy value `tle` maps to `sgp4`. For osculating Keplerian element fitting, use [`oem-to-opm`](OEM_TO_OPM.md).

### Synopsis

```bash
oem-to-omm [-h] -o <output_omm|-> [--fit-model <brouwer|dsst|sgp4>]
            [--mode <brouwer|dsst|tle>] [--theory <theory>]
            [--mu <value>] [--fit-span <duration>]
            [--object-name <name>] [--object-id <YYYY-NNNP>]
            [--tle-refinement <none|cartesian|keplerian>]
            [--tle-norad-cat-id <0..99999>] [--tle-classification-type <U|C|S>]
            [--tle-ephemeris-type <0..9>] [--tle-element-set-no <0..9999>]
            [--tle-rev-at-epoch <0..99999>]
            [--fit-report <path|->] [--no-fit-report]
            [--source-model <model>] [--source-report <path>]
            [-v] <input_oem|->
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input_oem>` | Path to input CCSDS OEM file (use `-` to read from stdin) |
| `-o`, `--output` | Save the fitted OMM to a file or `-` for stdout (required) |
| `-v`, `--verbose` | Print detailed debug information to stderr |
| `--fit-model` | Mean-element model: `brouwer`, `dsst`, or `sgp4` (default: `sgp4`) |
| `--mode` | Deprecated alias for `--fit-model`; legacy value `tle` maps to `sgp4` |
| `--theory` | Override OMM `MEAN_ELEMENT_THEORY`; must match the selected model (`BROUWER`/`BROUWER-LYDDANE`, `DSST`, or `SGP4`) |
| `--mu` | Gravitational parameter in m³/s² (default: Earth WGS-84) |
| `--fit-span` | Maximum fit/comparison span; accepts durations such as `2h`, `90m`, or `3600s` (default: `2h`). The SGP4 element and B* estimates use the supplied arc. |
| `--object-name` | OBJECT_NAME: Spacecraft name for OMM output |
| `--object-id` | OBJECT_ID: International designator (e.g., 1998-067A) |
| `--tle-refinement` | SGP4-fit epoch refinement: `cartesian` (default), `keplerian`, or `none` |
| `--tle-norad-cat-id` | TLE NORAD catalog number (0-99999, default: 0) |
| `--tle-classification-type` | TLE classification: `U`, `C`, or `S` (default: `U`) |
| `--tle-ephemeris-type` | TLE ephemeris type, integer 0-9 (default: 2) |
| `--tle-element-set-no` | TLE element set number (0-9999, default: 999) |
| `--tle-rev-at-epoch` | TLE revolution number at epoch (0-99999, default: 0) |
| `--fit-report` | Write JSON fit diagnostics to a path or `-` for stdout |
| `--no-fit-report` | Disable automatic fit-report creation |
| `--source-model` | Input provenance model label (default: `auto`) |
| `--source-report` | JSON provenance report describing the input |

### Input Format

Input must be a CCSDS OEM file, supplied as a path or `-` for stdin. The command does not accept a bare file of raw state rows. At least two state vectors are required. OEM position and velocity values use the standard km and km/s units and are converted internally to m and m/s. The OEM reference frame is not transformed by this command; provide states in a frame compatible with the selected fitting and propagation model.

### Output Format

The command writes a CCSDS OMM, either to the required output path or to stdout when the destination is `-`. Even for `--fit-model sgp4`, it does not write TLE text directly; convert the resulting SGP4 OMM with `omm-to-tle` if TLE lines are needed. With `-v`, a human-readable fit summary is also emitted; when the OMM goes to stdout, the summary goes to stderr.

```text
CCSDS_OMM_VERS = 2.0
...
MEAN_ELEMENT_THEORY = SGP4
```

### Refinement Methods

The script supports three TLE refinement strategies selected with `--tle-refinement` for matching TLE elements to the epoch state:

#### Cartesian refinement (`--tle-refinement cartesian`, default)

- Minimizes SGP4 Cartesian state residual at epoch
- Uses TudatPy for SGP4 propagation
- Refines the six mean-element parameters against the epoch Cartesian state
- Uses Gauss-Newton iteration with backtracking line search

#### Keplerian refinement (`--tle-refinement keplerian`)

- Minimizes osculating Keplerian element residual
- Uses `core.convert_tle.tle_to_osculating_keplerian` with J2 short-period corrections
- Uses Brouwer first-order J2 corrections to compare mean and osculating elements

#### No refinement (`--tle-refinement none`)

- Skips epoch state matching entirely
- Uses only regression-based mean element estimation
- Skips epoch-state refinement; later SGP4 arc scoring still requires TudatPy

### Estimation Pipeline

The SGP4 fit follows this workflow. Its mean-element and B* estimates use the full supplied arc; `--fit-span` limits the comparison window reported by the command.

1. **Parse input** — Read a CCSDS OEM and require at least two states.
2. **Initial estimate** — Estimate SGP4-compatible mean elements from the arc.
3. **Epoch refinement** — Optionally refine the epoch state using the selected method.
4. **B* estimation** — Search bounded B* values using sampled post-epoch states.
5. **Output** — Write the fitted values as an SGP4-theory OMM and fit diagnostics.

### Dependencies

- TudatPy (required for SGP4 propagation used by the SGP4 fit, including its arc scoring)
- NumPy
- `ephem_toolkit.core.ccsds.oem`, `ephem_toolkit.core.consts`, `ephem_toolkit.core.time_utils`, `ephem_toolkit.core.tle`
- `ephem_toolkit.oem_to_omm.fit_common`, `ephem_toolkit.oem_to_omm.fit_tle_main`
- `ephem_toolkit.oem_to_omm.fit_tle` components

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

- Use at least 2 state vectors (more can improve trend estimation)
- Span at least one orbital period for accurate mean motion estimation
- Ensure consistent time spacing for best regression results
- Verify the OEM reference frame is compatible with the selected model; this command does not transform frames

### Refinement Method Selection

- Use **Cartesian refinement** when you want direct SGP4 Cartesian matching at the epoch
- Use **Keplerian refinement** to avoid Cartesian epoch-state refinement; the overall SGP4 fit still requires TudatPy for propagation and arc scoring
- Use **no refinement** to skip epoch-state matching, not to avoid the SGP4 dependency

### B* Drag Term

- The script estimates B* from the arc; inspect the fit report before treating the estimate as physically meaningful
- The CLI has no option to provide a fixed B* value

### Fit Reports

By default, a JSON fit report is written alongside the OMM output using the `.fit.json` suffix. If the OMM is written to stdout, the input filename is used to derive the report path; when both input and output are stdin/stdout, no path can be inferred. Use `--fit-report <path>` to choose a destination or `--no-fit-report` to disable automatic report creation. In Brouwer mode, the report is written only when the OMM destination is a file. Do not direct both the OMM and fit report to stdout because the two formats will be concatenated.

### Metadata

- Provide accurate satellite metadata (NORAD number, international designator) when available
- Use meaningful satellite names for better TLE identification
- Increment element set number for successive TLE generations

## Troubleshooting

### "Need at least 2 OEM-like state vectors"

- Ensure the OEM contains at least 2 valid state records
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

- Verify input reference frame compatibility; this command does not transform frames
- Check for data gaps or outliers in input arc
- Consider using longer arc for B* estimation

## Performance Considerations
Runtime depends on the number of supplied OEM records, the number of refinement iterations, and the SGP4 evaluations used during B* estimation. No fixed runtime or accuracy is guaranteed.

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

`oem-to-omm` estimates SGP4-compatible mean elements from a CCSDS OEM arc and serializes them as an OMM. Convert that SGP4 OMM to TLE text with `omm-to-tle`. Mean elements are not the same as raw osculating Cartesian states, so this is an estimation problem.

### Repository context

Related commands and modules:

- `oem-to-omm` — fit mean elements from a CCSDS OEM and write an OMM
- `ephem_toolkit.core.tle` — shared `Tle` dataclass, `read_tle()`, and `write_tle()` functions
- `omm-to-tle` — convert an SGP4 OMM to TLE text
- `propagate-tle` — propagate a TLE with TudatPy SGP4 and print OEM-like states
- `propagate-omm` — propagate an OMM or TLE input and emit OEM output with automatic solver selection

### Overall pipeline

The SGP4 fit follows this workflow:

1. Read the CCSDS OEM states.
2. Estimate initial SGP4-compatible mean elements.
3. Optionally refine the epoch state.
4. Estimate `B*` from sampled post-epoch states.
5. Write an OMM and fit diagnostics.

---

## Stage 1 — parsing
The CLI reads a CCSDS OEM through `ephem_toolkit.core.ccsds.oem.CcsdsOem`. It requires at least two state records and converts the OEM km/km/s states to SI internally. The SGP4 element and B* estimation paths use all supplied records; `--fit-span` limits the diagnostics comparison window.

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
- finite-difference and line-search SGP4 evaluations are batched where supported

### 3b. Keplerian refinement (`--tle-refinement keplerian`)

### `refine_estimated_fields_keplerian_match`

This refinement step does not itself call SGP4. It minimizes the residual between the TLE's osculating Keplerian elements (computed via `core.convert_tle.tle_to_osculating_keplerian` with J2 short-period corrections) and the reference osculating elements derived from the input Cartesian state. The full SGP4 fit still requires TudatPy for subsequent arc scoring.

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

- J2 short-period corrections provide a differentiable mapping from TLE mean elements to osculating elements

---

## Stage 4 — `B*` estimation over the arc

### `estimate_bstar_from_arc`

The CLI estimates `B*` by minimizing propagated-state mismatch over selected post-epoch samples. The command-line interface does not expose a fixed-B* override.

### Strategy

1. Select a subset of representative arc samples.
2. For each candidate `B*`, build a TLE and propagate it to those sample times.
3. Compute a weighted total residual cost.
4. Use a simple one-dimensional search strategy to improve `B*`.

This is a bounded scalar search over the drag-like parameter.

---

## Supporting algorithms

| Component | Role |
|---|---|
| `linear_regression_slope` / `linear_regression_intercept` | Ordinary least-squares trend estimation |
| `solve_linear_system` | Gaussian elimination |
| `solve_weighted_least_squares` | Normal-equation least-squares solve with regularization |
| `solve_weighted_least_squares` | Weighted least-squares solve |
| `unwrap_angles_rad` | Angle unwrapping across `2π` discontinuities |
| `circular_mean_angle_rad` | Circular mean via `atan2(sum sin, sum cos)` |
| `circular_blend_angle_rad` | Weighted shortest-arc blending of angles |
| `format_tle_exponential_from_float` | Compact TLE exponential formatting |

---

## Design choices

- The SGP4 fit estimates elements separately from OMM serialization; use `omm-to-tle` to produce TLE text.
- Circular statistics are used extensively to avoid 0°/360° discontinuity problems.
- Epoch refinement is optional; SGP4 propagation is still used for arc scoring.

## Practical takeaway

Use:

- `core.tle.write_tle()` when you already know the TLE fields and want to write them programmatically
- `oem-to-omm` when you have a CCSDS OEM arc and want fitted mean elements in OMM form
- `omm-to-tle` when you want TLE text from an SGP4 OMM
- `core.tle.read_tle()` when you want to parse an existing TLE into structured fields

### Usage Examples

**Fit Brouwer mean elements:**

```bash
oem-to-omm --fit-model brouwer input.oem -o output.omm
```

**Fit DSST mean elements:**

```bash
oem-to-omm --fit-model dsst input.oem -o output.omm
```

**Fit SGP4-compatible mean elements:**

```bash
oem-to-omm --fit-model sgp4 input.oem -o output.omm
```

**Read an OEM from stdin and write the OMM to stdout:**

```bash
cat input.oem | oem-to-omm --fit-model sgp4 - -o -
```

**Use Keplerian epoch refinement:**

```bash
oem-to-omm --fit-model sgp4 --tle-refinement keplerian input.oem -o output.omm
```

**Fit without epoch-state refinement:**

```bash
oem-to-omm --fit-model sgp4 --tle-refinement none input.oem -o output.omm
```

**Specify satellite metadata:**

```bash
oem-to-omm --fit-model sgp4 input.oem -o output.omm \
  --object-name "ISS (ZARYA)" \
  --object-id "1998-067A" \
  --tle-norad-cat-id 25544 \
  --tle-classification-type U \
  --tle-element-set-no 999
```

**Fit a 3-hour arc and print verbose diagnostics:**
**Set a 3-hour fit/comparison span and print verbose diagnostics:**
**Set the SGP4 diagnostic comparison window to 3 hours:**

```bash
oem-to-omm --fit-model sgp4 --fit-span 3h -v input.oem -o output.omm
```

### Dependencies

- Python standard library
- NumPy (for numerical computations)
- TudatPy (required for SGP4 propagation in SGP4 fitting)
- `ephem_toolkit.core.tle` — TLE dataclass and formatting
- `ephem_toolkit.core.kepler` — Keplerian element conversions
- `ephem_toolkit.core.ccsds.oem` — OEM parsing
