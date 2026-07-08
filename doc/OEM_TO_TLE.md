# OEM to TLE Conversion

Comprehensive documentation for the `oem_to_tle` module, which estimates Two-Line Element (TLE) sets from OEM-like Cartesian state vectors.

## Overview

The `oem_to_tle` module provides tools for converting orbit ephemeris data in OEM (Orbit Ephemeris Message) format or raw Cartesian state vectors into TLE (Two-Line Element) format. This is a non-trivial estimation problem because TLEs encode SGP4-compatible mean orbital elements rather than osculating Cartesian states.

## Module Structure

The `oem_to_tle/` directory contains:

- `oem_to_tle.py` — Main executable script for TLE estimation
- `constants.py` — Physical and mathematical constants
- `estimation.py` — Core estimation algorithms for TLE elements
- `evaluation.py` — Evaluation and accuracy assessment tools
- `io_utils.py` — Input/output and parsing utilities
- `linalg.py` — Linear algebra utilities
- `models.py` — Data models and dataclasses
- `orbital_mechanics.py` — Orbital mechanics calculations
- `refinement.py` — Refinement algorithms for epoch state matching
- `tle_builder.py` — TLE construction and formatting
- `build_tle.md` — Detailed algorithm documentation
- `evaluate_build_tle_from_oem.py` — Round-trip accuracy evaluation tool

## Main Script: `oem_to_tle.py`

### Purpose

Estimates a valid Two-Line Element (TLE) set from a time series of OEM-like Cartesian state vectors with position in km and velocity in km/s.

### Synopsis

```bash
python oem_to_tle/oem_to_tle.py [-h] [-o <output.tle>] [--name <name>] 
                                 [--satellite-number <num>] [--classification <U|C|S>]
                                 [--int-designator-year <year>] 
                                 [--int-designator-launch-number <num>]
                                 [--int-designator-piece <piece>]
                                 [--ephemeris-type <type>] [--element-set-number <num>]
                                 [--bstar <value>] [--mean-motion-second-derivative <value>]
                                 [--revolution-number-at-epoch <num>]
                                 [--refinement <none|cartesian|keplerian>]
                                 [<input.dat>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input.dat>` | Input OEM-like state-vector file path or `-` for stdin (default: `-`) |
| `-o`, `--output` | Output TLE file path or `-` for stdout (default: `-`) |
| `--name` | Optional satellite name written above line 1 |
| `--satellite-number` | NORAD satellite number (0-99999, default: 99999) |
| `--classification` | Classification code: `U`, `C`, or `S` (default: `U`) |
| `--int-designator-year` | International designator launch year (0-99, default: 0) |
| `--int-designator-launch-number` | International designator launch number (0-999, default: 0) |
| `--int-designator-piece` | International designator piece identifier (default: `A`) |
| `--ephemeris-type` | Ephemeris type value (0-9, default: 0) |
| `--element-set-number` | Element set number (0-9999, default: 1) |
| `--bstar` | B* drag term in TLE exponential format (default: `00000+0`) |
| `--mean-motion-second-derivative` | Second derivative of mean motion (default: `00000+0`) |
| `--revolution-number-at-epoch` | Revolution number at epoch (0-99999, default: 0) |
| `--refinement` | Refinement method: `cartesian` (default), `keplerian`, or `none` |

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

The script supports three refinement strategies for matching TLE elements to the epoch state:

#### Cartesian Refinement (`--refinement cartesian`, default)

- Minimizes SGP4 Cartesian state residual at epoch
- Requires TudatPy for SGP4 propagation
- Provides highest accuracy for position and velocity matching
- Uses Gauss-Newton iteration with backtracking line search
- Typical accuracy: sub-meter position, sub-mm/s velocity

#### Keplerian Refinement (`--refinement keplerian`)

- Minimizes osculating Keplerian element residual
- Uses `common.kepler.tle_to_osculating_keplerian` with J2 short-period corrections
- No SGP4/TudatPy dependency (pure Python + NumPy)
- Excellent angular accuracy (sub-millidegree)
- Semi-major axis accuracy limited to ~2 km by first-order Brouwer approximation

#### No Refinement (`--refinement none`)

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

See [`oem_to_tle/build_tle.md`](oem_to_tle/build_tle.md) for detailed algorithm documentation.

### Usage Examples

**Basic usage with stdin/stdout:**

```bash
cat states.txt | python oem_to_tle/oem_to_tle.py
```

**Read from file, write to file:**

```bash
python oem_to_tle/oem_to_tle.py input.oem -o output.tle
```

**Specify satellite metadata:**

```bash
python oem_to_tle/oem_to_tle.py input.oem -o output.tle \
  --name "ISS (ZARYA)" \
  --satellite-number 25544 \
  --int-designator-year 98 \
  --int-designator-launch-number 67 \
  --int-designator-piece A
```

**Use Keplerian refinement (no TudatPy required):**

```bash
python oem_to_tle/oem_to_tle.py input.oem --refinement keplerian
```

**Skip refinement for quick estimate:**

```bash
python oem_to_tle/oem_to_tle.py input.oem --refinement none
```

**Specify B* drag term:**

```bash
python oem_to_tle/oem_to_tle.py input.oem --bstar "12345-4"
```

### Output Summary

The script prints a detailed summary including:

- Dataset statistics (record count, epoch range, span)
- Estimated TLE elements (mean and osculating values)
- Refinement accuracy metrics
- B* estimation results
- Keplerian element accuracy verification

Example output:

```text
Estimated TLE elements from OEM-like dataset:
  records: 145
  epoch range: 2026-05-20T12:00:00.000000 -> 2026-05-20T14:24:00.000000
  span [s]: 8640.000
  chosen TLE epoch: 2026-05-20T12:00:00.000000
  inclination-deg: 51.642345
  raan-deg: 123.456789
  eccentricity: 0.001234567
  arg-perigee-deg: 234.567890
  mean-anomaly-deg: 45.678901
  mean-motion-rev-per-day: 15.5432109876
  state-match-position-error-km: 0.000123
  state-match-velocity-error-km-s: 0.000000456
  semi-major-axis-km: 6793.456789
  bstar: 12345-4
  
  Accuracy verification (osculating Keplerian elements via common.kepler):
    semi-major-axis error:    +0.001234 km  (+1.234 m)
    eccentricity error:       +0.0000000123
    inclination error:        +0.000123 deg
    RAAN error:               +0.000234 deg
    arg-perigee error:        +0.000345 deg
    true-anomaly error:       +0.000456 deg
    arg-latitude (ω+θ) error: +0.000567 deg
```

### Dependencies

- Python standard library
- NumPy (for numerical computations)
- `common.tle` — TLE dataclass and formatting
- `common.kepler` — Keplerian element conversions
- `common.oem` — OEM parsing
- TudatPy (optional, required for `--refinement cartesian`)

## Evaluation Tool: `evaluate_build_tle_from_oem.py`

### Purpose

Evaluates OEM-to-TLE round-trip accuracy by generating a TLE from an OEM reference, propagating it with SGP4, and comparing position/velocity errors.

### Synopsis

```bash
python oem_to_tle/evaluate_build_tle_from_oem.py [-h] [--refinement <method>] 
                                                   [-d <duration>] [-s <step>] 
                                                   [<oem_file>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<oem_file>` | Path to reference OEM file (default: `test/ISS_2026-05-20.OEM`) |
| `--refinement` | Refinement method: `cartesian` (default), `keplerian`, or `none` |
| `-d`, `--duration` | Propagation duration (e.g., `1d`, `12h`, `3600s`) |
| `-s`, `--step` | Propagation step size (e.g., `10m`, `300s`). Default: matches OEM step |

### Usage Examples

**Evaluate with default settings:**

```bash
python oem_to_tle/evaluate_build_tle_from_oem.py
```

**Evaluate custom OEM file:**

```bash
python oem_to_tle/evaluate_build_tle_from_oem.py test/LEO3.oem
```

**Evaluate with Keplerian refinement:**

```bash
python oem_to_tle/evaluate_build_tle_from_oem.py --refinement keplerian
```

**Evaluate for 12 hours with 5-minute steps:**

```bash
python oem_to_tle/evaluate_build_tle_from_oem.py -d 12h -s 5m
```

### Dependencies

- TudatPy (for SGP4 propagation)
- NumPy
- `common.oem`, `common.common`
- `oem_to_tle/oem_to_tle.py`
- `propagation/propagate_tle.py`

## Algorithm Details

For detailed information about the estimation algorithms, refinement strategies, and implementation details, see:

- [`oem_to_tle/build_tle.md`](oem_to_tle/build_tle.md) — Comprehensive algorithm documentation

Key algorithmic features:

- **Secular trend fitting** — Ordinary least-squares regression for mean motion, RAAN, and argument of latitude
- **Circular statistics** — Robust angle estimation avoiding 0°/360° discontinuities
- **Phase matching** — Short-period filtering via orbital phase alignment
- **J2 nodal precession** — Mean inclination inference from RAAN drift
- **Gauss-Newton refinement** — Iterative epoch state matching with backtracking line search
- **B* optimization** — Drag term estimation via arc propagation error minimization

## Related Tools

- `common/tle.py` — TLE dataclass, `read_tle()`, and `write_tle()` functions
- `common/kepler.py` — Keplerian element conversions with J2 corrections
- `common/oem.py` — OEM parsing utilities
- `propagation/propagate_tle.py` — TLE propagation with SGP4
- `tle/omm_to_tle.py` — Convert OMM to TLE
- `tle/tle_to_omm.py` — Convert TLE to OMM

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

- [TLE.md](TLE.md) — TLE utilities overview
- [PROPAGATION.md](PROPAGATION.md) — Orbit propagation tools
- [README.md](README.md) — Repository overview
