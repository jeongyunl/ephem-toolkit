# tudatpy-utils

Miscellaneous utilities for orbit analysis and comparison.

## Available scripts

- `bin/state_diff.py`
- `bin/slice_oem.py`
- `plotting/plot_orbits.py`
- `plotting/plot_dependent_variables.py`

## `bin/state_diff.py`

Compares two OEM-like Cartesian states and reports differences in time, position, and velocity.

### Synopsis

```bash
python3 bin/state_diff.py [-h] [-v] [<state1.dat>] [<state2.dat>]
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
python3 bin/state_diff.py state1.dat state2.dat
```

**Compare with verbose output:**

```bash
python3 bin/state_diff.py -v state1.dat state2.dat
```

**Read first state from file, second from stdin:**

```bash
echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515" \
  | python3 bin/state_diff.py state1.dat -
```

**Read both states from stdin:**

```bash
(echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198"; \
 echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515") \
  | python3 bin/state_diff.py
```

**Show help:**

```bash
python3 bin/state_diff.py -h
```

### Dependencies

- NumPy
- local helper modules `common.common`, `common.oem`, `common.time_utils`

## `bin/slice_oem.py`

Slices CCSDS OEM files by index or time range, with optional interpolation.

See [SLICE_OEM.md](SLICE_OEM.md) for complete documentation.

## `plotting/plot_orbits.py`

Plots multiple orbit trajectories with various views and RTN (Radial-Transverse-Normal) coordinates.

### Synopsis

```bash
python3 plotting/plot_orbits.py [-h] [-o <output_file>] [-d <duration>] [--time-unit <unit>] <reference_oem> [<comparison_oem1>] [<comparison_oem2>] ...
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
python3 plotting/plot_orbits.py reference.oem
```

**Plot reference orbit with comparison orbits:**

```bash
python3 plotting/plot_orbits.py reference.oem comparison1.oem comparison2.oem
```

**Save output to files:**

```bash
python3 plotting/plot_orbits.py reference.oem comparison.oem -o orbits.png
```

**Analyze only first 2 hours:**

```bash
python3 plotting/plot_orbits.py reference.oem comparison.oem -d 2h
```

**Use minutes for time-series x-axis:**

```bash
python3 plotting/plot_orbits.py reference.oem comparison.oem --time-unit minutes
```

**Show help:**

```bash
python3 plotting/plot_orbits.py -h
```

### Dependencies

- NumPy
- Matplotlib
- local helper modules `common.common`, `common.time_utils`, `common.oem`, `common.interpolator.lagrange`
