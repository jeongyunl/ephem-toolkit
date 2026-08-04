# tudatpy-utils

Miscellaneous utilities for orbit analysis and comparison.

## Available scripts

- `bin/diff_oem.py`
- `bin/slice_oem.py`
- `bin/ecef_to_aer.py`
- `plotting/plot_orbit_deltas.py`
- `plotting/plot_dependent_variables.py`

## `bin/diff_oem.py`

Compares corresponding states from two CCSDS OEM files and reports position and
velocity differences. Without interpolation, states are compared sequentially
by index, stopping at the shorter history. Supports optional transformation
stages (rotation fitting and time-shift correction) to align comparison data
with reference data before computing differences.

### Synopsis

```bash
python3 bin/diff_oem.py [-h] [-v] [--debug] [--interpolate] \
  [--interpolate-ref] [--interpolate-data] [--rtn] \
  [--rot] [--rot-xy] [--rot-z] [--time-shift] \
  [--rot-fit-span <duration>] \
  [--start <iso8601|duration>] [--stop <iso8601|duration>] \
  <reference_oem.oem> <comparison_oem.oem>
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-v`, `--verbose` | Print detailed component-wise differences |
| `--debug` | Print input, overlap, requested, and effective time ranges to stderr |
| `--interpolate` | Interpolate both OEM histories at the other history's epochs |
| `--interpolate-ref` | Interpolate the reference OEM at each comparison-state timestamp |
| `--interpolate-data` | Interpolate comparison data at each reference-state timestamp |
| `--rtn` | Include position and velocity differences in the reference RTN frame |
| `--rot` | Fit a fixed 3D rotation from initial comparison state span and apply it before reporting differences (may be repeated) |
| `--rot-xy` | Fit a fixed rotation around X and Y axes from initial comparison state span (may be repeated) |
| `--rot-z` | Fit a fixed rotation around Z axis from initial comparison state span (may be repeated) |
| `--time-shift` | Fit a constant comparison epoch bias and shift comparison timestamps before reporting differences (may be repeated) |
| `--rot-fit-span <duration>` | Duration of the initial state span used for rotation fitting (default: 1 hour) |
| `--start <iso8601|duration>` | Start of the comparison window; durations are relative to the first reference epoch |
| `--stop <iso8601|duration>` | End of the comparison window; durations are relative to the resolved start time |
| `<reference_oem.oem>` | Reference CCSDS OEM file path or `-` to read from stdin |
| `<comparison_oem.oem>` | Comparison CCSDS OEM file path or `-` to read from stdin |

### Behavior

- Reads CCSDS OEM state histories, preserving their native timestamps and state vectors
- Computes position and velocity difference magnitudes for each compared state
- Computes time differences only when interpolation is disabled
- Without interpolation, compares states sequentially by index
- With `--interpolate-ref`, evaluates reference data at comparison timestamps
- With `--interpolate-data`, evaluates comparison data at reference timestamps
- `--interpolate` is equivalent to specifying both interpolation options
- Interpolation queries are limited to the overlapping time range of both OEM files
- `--start` and `--stop` further restrict comparisons to the overlapping time range
- States outside the interpolation range are skipped
- With `-v`, prints component-wise differences for each axis
- With `--rtn`, prints the differences expressed in the reference radial-transverse-normal frame
- With `--debug`, prints range calculations to stderr
- Accepts file paths or stdin (`-`) as input sources
- If both input paths are `-`, the command reports an argument error

#### Transformation Stages

The tool supports optional transformation stages that fit and apply corrections to the comparison data before computing differences:

- **`--rot`**: Fits a full 3D rotation matrix using SVD decomposition to align comparison positions with reference positions. Uses the initial time span specified by `--rot-fit-span`.
- **`--rot-xy`**: Fits a rotation around X and Y axes only (constrains Z-axis rotation to zero). Useful when Z-axis alignment is already correct.
- **`--rot-z`**: Fits a rotation around Z axis only (constrains X and Y rotations to zero). Useful for correcting azimuthal misalignment.
- **`--time-shift`**: Fits a constant time bias to minimize position differences between comparison and reference states. Uses golden-section search optimization over a ±1800s window.
- **`--rot-fit-span`**: Controls the duration of data used for rotation fitting (default: 1 hour from the start of the overlap).

Transformation stages can be repeated and are applied in the order specified on the command line. Each stage produces:
1. A "Normal comparison" report showing differences before any transformations
2. Intermediate comparison reports after each transformation stage
3. Fitted transformation parameters (rotation matrices with Euler angles, time shifts)
4. Summary statistics for each comparison

The rotation fitting uses position data only, but the fitted rotation is applied to both position and velocity components.

### Input format

Standard CCSDS OEM files containing Cartesian position and velocity states.

### Output format

The script prints a comparison summary including:

- Reference and comparison epochs
- Time difference in seconds when interpolation is disabled
- Position difference magnitude in km
- Velocity difference magnitude in km/s
- (With `-v`) Component-wise differences for each axis
- (With `--rtn`) Position and velocity differences in the reference RTN frame

### Usage

**Compare two OEM files:**

```bash
python3 bin/diff_oem.py reference.oem comparison.oem
```

**Compare with verbose output:**

```bash
python3 bin/diff_oem.py -v reference.oem comparison.oem
```

**Interpolate the reference history:**

```bash
python3 bin/diff_oem.py --interpolate-ref reference.oem comparison.oem
```

**Interpolate comparison data:**

```bash
python3 bin/diff_oem.py --interpolate-data reference.oem comparison.oem
```

**Interpolate both histories:**

```bash
python3 bin/diff_oem.py --interpolate reference.oem comparison.oem
```

**Compare a time window with RTN output and debug ranges:**

```bash
python3 bin/diff_oem.py --start 2026-01-01T00:00:00 --stop 2h \
  --rtn --debug reference.oem comparison.oem
```

**Fit and apply a 3D rotation to align comparison with reference:**

```bash
python3 bin/diff_oem.py --rot reference.oem comparison.oem
```

**Fit and apply a Z-axis rotation only:**

```bash
python3 bin/diff_oem.py --rot-z reference.oem comparison.oem
```

**Fit and apply a time shift to align epochs:**

```bash
python3 bin/diff_oem.py --time-shift reference.oem comparison.oem
```

**Apply multiple transformations in sequence (rotation then time-shift):**

```bash
python3 bin/diff_oem.py --rot --time-shift reference.oem comparison.oem
```

**Use custom rotation fitting span (first 30 minutes):**

```bash
python3 bin/diff_oem.py --rot --rot-fit-span 1800 reference.oem comparison.oem
```

**Show help:**

```bash
python3 bin/diff_oem.py -h
```

### Dependencies

- NumPy
- local helper modules `common.oem`, `common.time_utils`, and `common.interpolator.lagrange`

## `bin/slice_oem.py`

Slices CCSDS OEM files by index or time range, with optional interpolation.

See [SLICE_OEM.md](SLICE_OEM.md) for complete documentation.

## `bin/ecef_to_aer.py`

Converts ECEF OEM ephemeris data to AER (Azimuth-Elevation-Range) coordinates relative to a ground station.

### Synopsis

```bash
python3 bin/ecef_to_aer.py [-h] [-v] [-o <output>] --lat <degrees> --lon <degrees> --alt <meters> [<oem_file>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<oem_file>` | Path to input CCSDS OEM file in ECEF frame (use `-` or omit to read from stdin) |
| `--lat`, `--latitude` | Ground station latitude in degrees (positive = North, negative = South) |
| `--lon`, `--longitude` | Ground station longitude in degrees (positive = East, negative = West) |
| `--alt`, `--altitude` | Ground station altitude above WGS-84 ellipsoid in meters |
| `-o`, `--output` | Output file path (default: `-` for stdout) |
| `-v`, `--verbose` | Print detailed debug information to stderr |

### Behavior

- Reads CCSDS OEM files with ECEF reference frame
- Converts position vectors to AER coordinates relative to a ground station
- Ground station is specified in geodetic coordinates (latitude, longitude, altitude)
- Only positions are converted; velocities are not converted to AER rates
- Outputs timestamp, azimuth, elevation, and range for each state

### Input format

Standard CCSDS OEM file with ECEF reference frame (e.g., ITRF, ECEF).

### Output format

Each line contains:

```text
<ISO-8601 timestamp>  <azimuth_deg>  <elevation_deg>  <range_m>
```

- **timestamp**: ISO 8601 format (e.g., `2024-01-01T00:00:00.000000`)
- **azimuth**: Azimuth angle in degrees (0° = North, 90° = East)
- **elevation**: Elevation angle in degrees (0° = horizon, 90° = zenith)
- **range**: Distance in meters

### Usage

**Convert ISS orbit to AER from ground station:**

```bash
python3 bin/ecef_to_aer.py iss.oem --lat 40.7128 --lon -74.0060 --alt 10.0
```

**Read from stdin:**

```bash
cat iss.oem | python3 bin/ecef_to_aer.py --lat 40.7128 --lon -74.0060 --alt 10.0
```

**Save output to file:**

```bash
python3 bin/ecef_to_aer.py iss.oem --lat 51.5074 --lon -0.1278 --alt 0.0 -o aer_data.txt
```

**Verbose output:**

```bash
python3 bin/ecef_to_aer.py iss.oem --lat 40.7128 --lon -74.0060 --alt 10.0 -v
```

**Show help:**

```bash
python3 bin/ecef_to_aer.py -h
```

### Dependencies

- NumPy
- local helper modules `common.aer`, `common.oem`, `common.time_utils`

## `plotting/plot_orbit_deltas.py`

Plots multiple orbit trajectories with various views and RTN (Radial-Transverse-Normal) coordinates.

### Synopsis

```bash
python3 plotting/plot_orbit_deltas.py [-h] [-o <output_file>] [-d <duration>] [--time-unit <unit>] <reference_oem> [<comparison_oem1>] [<comparison_oem2>] ...
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
python3 plotting/plot_orbit_deltas.py reference.oem
```

**Plot reference orbit with comparison orbits:**

```bash
python3 plotting/plot_orbit_deltas.py reference.oem comparison1.oem comparison2.oem
```

**Save output to files:**

```bash
python3 plotting/plot_orbit_deltas.py reference.oem comparison.oem -o orbits.png
```

**Analyze only first 2 hours:**

```bash
python3 plotting/plot_orbit_deltas.py reference.oem comparison.oem -d 2h
```

**Use minutes for time-series x-axis:**

```bash
python3 plotting/plot_orbit_deltas.py reference.oem comparison.oem --time-unit minutes
```

**Show help:**

```bash
python3 plotting/plot_orbit_deltas.py -h
```

### Dependencies

- NumPy
- Matplotlib
- local helper modules `common.common`, `common.time_utils`, `common.oem`, `common.interpolator.lagrange`
