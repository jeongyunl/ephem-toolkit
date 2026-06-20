# tudatpy-utils

Miscellaneous utilities for orbit analysis and comparison.

## Available scripts

- `misc/state_diff.py`
- `misc/compare_interpolations.py`
- `misc/evaluate_build_tle_from_oem.py`
- `oem/oem_slice.py`
- `plotting/plot_orbits.py`

## `misc/state_diff.py`

Compares two OEM-like Cartesian states and reports differences in time, position, and velocity.

### Synopsis

```bash
python misc/state_diff.py [-h] [-v] [<state1.dat>] [<state2.dat>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-v`, `--verbose` | Print detailed component-wise differences |
| `<state1.dat>` | First OEM-like state file path or `-` to read from stdin (default: `-`) |
| `<state2.dat>` | Second OEM-like state file path or `-` to read from stdin (default: `-`) |

### Behavior

- Reads two OEM-like state lines (epoch + Cartesian position and velocity)
- Computes differences in time, position magnitude, and velocity magnitude
- With `-v`, prints component-wise differences for each axis
- Accepts file paths or stdin (`-`) as input sources
- If both state1 and state2 are `-`, reads two states sequentially from stdin

### Input format

Each state line must contain 7 fields:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Notes:

- **Epoch**: ISO 8601 timestamp such as `2025-11-10T15:42:27.000000`
- **Position**: X, Y, Z in kilometres
- **Velocity**: VX, VY, VZ in km/s
- Blank lines and lines beginning with `#` are skipped
- Parse failures are reported and the offending line is skipped

### Output format

The script prints a comparison summary including:

- State 1 and State 2 epochs
- Time difference in seconds
- Position difference magnitude in km
- Velocity difference magnitude in km/s
- (With `-v`) Component-wise differences for each axis

### Usage

**Compare two state files:**

```bash
python misc/state_diff.py state1.dat state2.dat
```

**Compare with verbose output:**

```bash
python misc/state_diff.py -v state1.dat state2.dat
```

**Read first state from file, second from stdin:**

```bash
echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515" \
  | python misc/state_diff.py state1.dat -
```

**Read both states from stdin:**

```bash
(echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198"; \
 echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515") \
  | python misc/state_diff.py
```

**Show help:**

```bash
python misc/state_diff.py -h
```

### Dependencies

- NumPy
- local helper module `common.common`

## `misc/compare_interpolations.py`

Compares different interpolation methods for orbit state data.

### Synopsis

```bash
python misc/compare_interpolations.py [-h] <input_file>
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input_file>` | Path to OEM or raw-state file to analyze |

### Behavior

- Reads an OEM or raw-state file containing orbit state history
- Compares multiple interpolation methods (e.g., Lagrange, cubic spline)
- Evaluates interpolation accuracy at intermediate points
- Generates plots comparing interpolation methods

### Input format

Accepts OEM files or raw state-vector files with lines in the format:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

### Output

The script generates Matplotlib figures comparing:

- Interpolation accuracy for different methods
- Position and velocity errors
- Computational performance metrics

### Usage

**Compare interpolation methods for an OEM file:**

```bash
python misc/compare_interpolations.py propagated.oem
```

**Compare interpolation methods for a raw state file:**

```bash
python misc/compare_interpolations.py states.txt
```

**Show help:**

```bash
python misc/compare_interpolations.py -h
```

### Dependencies

- NumPy
- Matplotlib
- TudatPy (for interpolators)
- local helper modules `common.common`, `common.oem`

## `oem/oem_slice.py`

Slices CCSDS OEM files by index or time range, with optional interpolation.

### Synopsis

```bash
python oem/oem_slice.py [-h] [-s <slice>] [-t <start[,stop[,step]]>] [-i] [--oem] <oem_file>
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-s`, `--slice` | Python-style slice index (e.g., `0:10`, `::2`, `5`, `-5:`) |
| `-t`, `--time-slice` | Time slice specifier using comma-separated values |
| `-i`, `--interpolate` | Enable interpolation when a step size is provided |
| `--oem` | Write sliced results in OEM format (default: raw state lines) |
| `<oem_file>` | Path to OEM file |

### Behavior

- Reads a CCSDS OEM file
- Slices states by index or time range
- Optionally interpolates states at specified step sizes
- Outputs either raw state lines or OEM format

### Index slicing

Use Python-style slice notation:

- `0:10` — states 0 through 9
- `::2` — every other state
- `5` — state at index 5
- `-5:` — last 5 states

### Time slicing

Format: `start[,stop[,step]]`

- `start` and `stop` may be ISO-8601 datetimes or durations (e.g., `10m`, `1h30m`, `1d`, `-10m`)
- `step` is a duration for interpolation (e.g., `30s`, `5m`, `1h`)
- If `stop` is omitted, only one matching state is returned
- Durations are relative to the OEM start time (positive) or end time (negative)

### Output format

Without `--oem`, outputs raw state lines:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

With `--oem`, outputs a valid CCSDS OEM file with updated metadata.

### Usage

**Slice by index (first 10 states):**

```bash
python oem/oem_slice.py -s 0:10 propagated.oem
```

**Slice by index (every other state):**

```bash
python oem/oem_slice.py -s ::2 propagated.oem
```

**Slice by time (first hour):**

```bash
python oem/oem_slice.py -t "0,1h" propagated.oem
```

**Slice by time with interpolation (10-minute steps):**

```bash
python oem/oem_slice.py -t "0,1h,10m" -i propagated.oem
```

**Slice by time (last 30 minutes):**

```bash
python oem/oem_slice.py -t "-30m," propagated.oem
```

**Output in OEM format:**

```bash
python oem/oem_slice.py -s 0:100 --oem propagated.oem > sliced.oem
```

**Show help:**

```bash
python oem/oem_slice.py -h
```

### Dependencies

- TudatPy (for interpolators)
- local helper modules `common.oem`

## `plotting/plot_orbits.py`

Plots multiple orbit trajectories with various views and RTN (Radial-Transverse-Normal) coordinates.

### Synopsis

```bash
python plotting/plot_orbits.py [-h] [-o <output_file>] [-d <duration>] [--time-unit <unit>] <reference_oem> [<comparison_oem1>] [<comparison_oem2>] ...
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<reference_oem>` | Path to reference OEM or raw-state file (required) |
| `<comparison_oem>` | Optional paths to comparison OEM or raw-state files |
| `-o`, `--output` | Output file path for saving figures (e.g., `orbits.png`) |
| `-d`, `--duration` | Duration of data to analyze from start (e.g., `1h`, `30m`, `3600s`) |
| `--time-unit` | Time unit for time series plots: `m`/`minute`/`minutes` or `h`/`hour`/`hours` (default: `hours`) |

### Behavior

- Reads one or more OEM or raw-state files
- First file is treated as the reference orbit
- Remaining files are comparison orbits
- Generates multiple plots comparing orbits in different coordinate systems
- Supports optional duration filtering and time-unit selection

### Input format

Accepts OEM files or raw state-vector files with lines in the format:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

### Output

The script generates Matplotlib figures showing:

1. **3D Orbit Trajectory** — 3D view of all orbits
2. **XY Plane** — X-Y projection
3. **XZ Plane** — X-Z projection
4. **YZ Plane** — Y-Z projection
5. **Relative Position Delta (Cartesian)** — Time series of position differences in X, Y, Z
6. **Relative Velocity Delta (Cartesian)** — Time series of velocity differences in VX, VY, VZ
7. **Relative Position Delta (RTN)** — Time series of position differences in Radial, Transverse, Normal
8. **Relative Velocity Delta (RTN)** — Time series of velocity differences in Radial, Transverse, Normal
9. **Relative Position Delta: Radial-Transverse** — 2D plot of relative position in RTN coordinates
10. **Relative Position Delta: Radial-Normal** — 2D plot of relative position in RTN coordinates
11. **Relative Velocity Delta: Radial-Transverse** — 2D plot of relative velocity in RTN coordinates
12. **Relative Velocity Delta: Radial-Normal** — 2D plot of relative velocity in RTN coordinates

If `-o` is provided, figures are saved with suffixes (e.g., `orbits_relative_rtn_timeseries.png`).
Otherwise, figures are displayed interactively.

### Usage

**Plot single orbit:**

```bash
python plotting/plot_orbits.py reference.oem
```

**Plot reference orbit with comparison orbits:**

```bash
python plotting/plot_orbits.py reference.oem comparison1.oem comparison2.oem
```

**Save output to files:**

```bash
python plotting/plot_orbits.py reference.oem comparison.oem -o orbits.png
```

**Analyze only first 2 hours:**

```bash
python plotting/plot_orbits.py reference.oem comparison.oem -d 2h
```

**Use minutes for time-series x-axis:**

```bash
python plotting/plot_orbits.py reference.oem comparison.oem --time-unit minutes
```

**Show help:**

```bash
python plotting/plot_orbits.py -h
```

### Dependencies

- NumPy
- Matplotlib
- TudatPy (for interpolators)
- local helper modules `common.common`, `common.oem`

## `misc/evaluate_build_tle_from_oem.py`

Evaluates `build_tle.py` round-trip accuracy by generating a TLE from an OEM reference, propagating it, and comparing position/velocity errors.

### Synopsis

```bash
python misc/evaluate_build_tle_from_oem.py [-h] [--refinement <none|cartesian|keplerian>] [-d <duration>] [-s <step>] [<oem_file>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<oem_file>` | Path to reference OEM file (default: `test/ISS_2026-05-20.OEM`) |
| `--refinement` | Refinement method: `cartesian` (default), `keplerian`, or `none` |
| `-d`, `--duration` | Propagation duration (e.g., `1d`, `12h`, `3600s`) |
| `-s`, `--step` | Propagation step size (e.g., `10m`, `300s`). Default: matches OEM step |

### Behavior

The script performs a round-trip evaluation workflow:

1. Reads an OEM reference file containing state vectors
2. Generates a TLE from the OEM using `build_tle.py` with specified refinement method
3. Propagates the generated TLE using `propagate_tle.py` over the evaluation span
4. Compares propagated states against the original OEM at matching epochs
5. Prints position and velocity error statistics

### Refinement methods

| Method | Description |
|---|---|
| `cartesian` | SGP4 Cartesian state matching (requires TudatPy) |
| `keplerian` | Osculating Keplerian element matching via `common.kepler` (no TudatPy needed) |
| `none` | Skip refinement |

### Output

The script prints:

- OEM reference span and step size
- Generated TLE lines
- Propagation configuration
- Position error statistics (min, max, mean, RMS)
- Velocity error statistics (min, max, mean, RMS)
- Position error at selected time offsets

### Usage

**Evaluate with default OEM and Cartesian refinement:**

```bash
python misc/evaluate_build_tle_from_oem.py
```

**Evaluate with custom OEM file:**

```bash
python misc/evaluate_build_tle_from_oem.py test/ISS_2026-05-20.OEM
```

**Evaluate with Keplerian refinement:**

```bash
python misc/evaluate_build_tle_from_oem.py --refinement keplerian
```

**Evaluate with no refinement:**

```bash
python misc/evaluate_build_tle_from_oem.py --refinement none
```

**Evaluate for 12 hours with 5-minute steps:**

```bash
python misc/evaluate_build_tle_from_oem.py -d 12h -s 5m
```

**Show help:**

```bash
python misc/evaluate_build_tle_from_oem.py -h
```

### Dependencies

- TudatPy (for SGP4 propagation and Cartesian refinement)
- NumPy
- local helper modules `common.oem`, `common.common`
- Requires `tle/build_tle.py` and `propagation/propagate_tle.py` to be available

---
